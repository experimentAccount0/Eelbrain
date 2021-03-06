"""
Boosting as described by David et al. (2007).

Profiling
---------
ds = datasets._get_continuous()
y = ds['y']
x1 = ds['x1']
x2 = ds['x2']

%prun -s cumulative res = boosting(y, x1, 0, 1)

"""
from __future__ import division
from inspect import getargspec
from itertools import chain, izip, product
from math import floor
from multiprocessing import Process, Queue
from multiprocessing.sharedctypes import RawArray
import signal
import time
from threading import Event, Thread

import numpy as np
from scipy.stats import spearmanr
from tqdm import tqdm

from .._config import CONFIG
from .._data_obj import NDVar, UTS, dataobj_repr
from .._stats.error_functions import (l1, l2, l1_for_delta, l2_for_delta,
                                      update_error)
from .._utils import LazyProperty
from .shared import RevCorrData


# BoostingResult version
VERSION = 6

# cross-validation
N_SEGS = 10

# process messages
JOB_TERMINATE = -1

# error functions
ERROR_FUNC = {'l2': l2, 'l1': l1}
DELTA_ERROR_FUNC = {'l2': l2_for_delta, 'l1': l1_for_delta}


class BoostingResult(object):
    """Result from boosting a temporal response function

    Attributes
    ----------
    h : NDVar | tuple of NDVar
        The temporal response function. Whether ``h`` is an NDVar or a tuple of
        NDVars depends on whether the ``x`` parameter to :func:`boosting` was
        an NDVar or a sequence of NDVars.
    h_scaled : NDVar | tuple of NDVar
        ``h`` scaled such that it applies to the original input ``y`` and ``x``.
        If boosting was done with ``scale_data=False``, ``h_scaled`` is the same
        as ``h``.
    r : float | NDVar
        Correlation between the measured response and the response predicted
        with ``h``. Type depends on the ``y`` parameter to :func:`boosting`.
    spearmanr : float | NDVar
        As ``r``, the Spearman rank correlation.
    t_run : float
        Time it took to run the boosting algorithm (in seconds).
    error : str
        The error evaluation method used.
    fit_error : float | NDVar
        The fit error, i.e. the result of the ``error`` error function on the
        final fit.
    delta : scalar
        Kernel modification step used.
    mindelta : None | scalar
        Mindelta parameter used.
    scale_data : bool
        Scale_data parameter used.
    y_mean : NDVar | scalar
        Mean that was subtracted from ``y``.
    y_scale : NDVar | scalar
        Scale by which ``y`` was divided.
    x_mean : NDVar | scalar | tuple
        Mean that was subtracted from ``x``.
    x_scale : NDVar | scalar | tuple
        Scale by which ``x`` was divided.
    """
    def __init__(self, h, r, isnan, t_run, version, delta, mindelta, error,
                 spearmanr, fit_error, scale_data, y_mean, y_scale, x_mean,
                 x_scale, y=None, x=None, tstart=None, tstop=None):
        self.h = h
        self.r = r
        self.isnan = isnan
        self.t_run = t_run
        self.version = version
        self.delta = delta
        self.mindelta = mindelta
        self.error = error
        self.spearmanr = spearmanr
        self.fit_error = fit_error
        self.scale_data = scale_data
        self.y_mean = y_mean
        self.y_scale = y_scale
        self.x_mean = x_mean
        self.x_scale = x_scale
        self.y = y
        self.x = x
        self.tstart = tstart
        self.tstop = tstop

    def __getstate__(self):
        return {attr: getattr(self, attr) for attr in
                getargspec(self.__init__).args[1:]}

    def __setstate__(self, state):
        self.__init__(**state)

    def __repr__(self):
        if self.x is None or isinstance(self.x, basestring):
            x = self.x
        else:
            x = ' + '.join(map(str, self.x))
        items = ['boosting %s ~ %s' % (self.y, x),
                 '%g - %g' % (self.tstart, self.tstop)]
        argspec = getargspec(boosting)
        names = argspec.args[-len(argspec.defaults):]
        for name, default in izip(names, argspec.defaults):
            value = getattr(self, name)
            if value != default:
                items.append('%s=%r' % (name, value))
        return '<%s>' % ', '.join(items)

    @LazyProperty
    def h_scaled(self):
        if self.y_scale is None:
            return self.h
        elif isinstance(self.h, NDVar):
            return self.h * (self.y_scale / self.x_scale)
        else:
            return tuple(h * (self.y_scale / sx) for h, sx in
                         izip(self.h, self.x_scale))

    def _set_parc(self, parc):
        """Change the parcellation of source-space result
         
        Notes
        -----
        No warning for missing sources!
        """
        if not self.r.has_dim('source'):
            raise RuntimeError('BoostingResult does not have source-space data')

        source = self.r.source
        source.set_parc(parc)
        index = np.invert(source.parc.startswith('unknown-'))

        def sub(x):
            if isinstance(x, tuple):
                return tuple(sub(x_) for x_ in x)
            assert x.source is source
            return x.sub(source=index)

        for attr in ('h', 'r', 'spearmanr', 'fit_error', 'y_mean', 'y_scale'):
            x = getattr(self, attr)
            if x is not None:
                setattr(self, attr, sub(x))


def boosting(y, x, tstart, tstop, scale_data=True, delta=0.005, mindelta=None,
             error='l2'):
    """Estimate a temporal response function through boosting

    Parameters
    ----------
    y : NDVar
        Signal to predict.
    x : NDVar | sequence of NDVar
        Signal to use to predict ``y``. Can be sequence of NDVars to include
        multiple predictors. Time dimension must correspond to ``y``.
    tstart : float
        Start of the TRF in seconds.
    tstop : float
        Stop of the TRF in seconds.
    scale_data : bool | 'inplace'
        Scale ``y`` and ``x`` before boosting: subtract the mean and divide by
        the standard deviation (when ``error='l2'``) or the mean absolute
        value (when ``error='l1'``). With ``scale_data=True`` (default) the
        original ``y`` and ``x`` are left untouched; use ``'inplace'`` to save
        memory by scaling the original ``y`` and ``x``.
    delta : scalar
        Step for changes in the kernel.
    mindelta : scalar
        If the error for the training data can't be reduced, divide ``delta``
        in half until ``delta < mindelta``. The default is ``mindelta = delta``,
        i.e. ``delta`` is constant.
    error : 'l2' | 'l1'
        Error function to use (default is ``l2``).

    Returns
    -------
    result : BoostingResult
        Object containing results from the boosting estimation (see
        :class:`BoostingResult`).

    Notes
    -----
    The boosting algorithm is described in [1]_.

    References
    ----------
    .. [1] David, S. V., Mesgarani, N., & Shamma, S. A. (2007). Estimating
        sparse spectro-temporal receptive fields with natural stimuli. Network:
        Computation in Neural Systems, 18(3), 191-212.
        `10.1080/09548980701609235 <https://doi.org/10.1080/09548980701609235>`_.
    """
    # check arguments
    mindelta_ = delta if mindelta is None else mindelta

    data = RevCorrData(y, x, error, scale_data)
    y_data = data.y
    x_data = data.x
    n_y = len(y_data)
    n_x = len(x_data)

    # prepare trf (by cropping data)
    tstep = data.time.tstep
    i_start = int(round(tstart / tstep))
    i_stop = int(round(tstop / tstep))
    trf_length = i_stop - i_start
    if i_start < 0:
        x_data = x_data[:, -i_start:]
        y_data = y_data[:, :i_start]
    elif i_start > 0:
        x_data = x_data[:, :-i_start]
        y_data = y_data[:, i_start:]

    # progress bar
    pbar = tqdm(desc="Boosting %i signals" % n_y if n_y > 1 else "Boosting",
                total=n_y * 10)
    # result containers
    res = np.empty((3, n_y))  # r, rank-r, error
    h_x = np.empty((n_y, n_x, trf_length))
    # boosting
    if CONFIG['n_workers']:
        # Make sure cross-validations are added in the same order, otherwise
        # slight numerical differences can occur
        job_queue, result_queue = setup_workers(
            y_data, x_data, trf_length, delta, mindelta_, N_SEGS, error)
        stop_jobs = Event()
        thread = Thread(target=put_jobs, args=(job_queue, n_y, N_SEGS, stop_jobs))
        thread.daemon = True
        thread.start()

        # collect results
        try:
            h_segs = {}
            for _ in xrange(n_y * N_SEGS):
                y_i, seg_i, h = result_queue.get()
                pbar.update()
                if y_i in h_segs:
                    h_seg = h_segs[y_i]
                    h_seg[seg_i] = h
                    if len(h_seg) == N_SEGS:
                        del h_segs[y_i]
                        hs = [h for h in (h_seg[i] for i in xrange(N_SEGS)) if
                              h is not None]
                        if hs:
                            h = np.mean(hs, 0, out=h_x[y_i])
                            res[:, y_i] = evaluate_kernel(y_data[y_i], x_data, h, error)
                        else:
                            h_x[y_i] = 0
                            res[:, y_i] = 0.
                else:
                    h_segs[y_i] = {seg_i: h}
        except KeyboardInterrupt:
            stop_jobs.set()
            raise
    else:
        for y_i, y_ in enumerate(y_data):
            hs = []
            for i in xrange(N_SEGS):
                h = boost_1seg(x_data, y_, trf_length, delta, N_SEGS, i,
                               mindelta_, error)
                if h is not None:
                    hs.append(h)
                pbar.update()

            if hs:
                h = np.mean(hs, 0, out=h_x[y_i])
                res[:, y_i] = evaluate_kernel(y_, x_data, h, error)
            else:
                h_x[y_i].fill(0)
                res[:, y_i].fill(0.)

    pbar.close()
    dt = time.time() - pbar.start_t

    # fit-evaluation statistics
    rs, rrs, errs = res
    isnan = np.isnan(rs)
    rs[isnan] = 0
    r = data.package_statistic(rs, 'r', 'correlation')
    rr = data.package_statistic(rrs, 'r', 'rank correlation')
    err = data.package_value(errs, 'fit error')

    y_mean, y_scale, x_mean, x_scale = data.data_scale_ndvars()

    return BoostingResult(data.package_kernel(h_x, tstart), r, isnan, dt, VERSION,
                          delta, mindelta, error, rr, err,
                          scale_data, y_mean, y_scale, x_mean, x_scale,
                          data.y_name, data.x_name, tstart, tstop)


def boost_1seg(x, y, trf_length, delta, nsegs, segno, mindelta, error,
               return_history=False):
    """Boosting with one test segment determined by regular division

    Based on port of svdboostV4pred

    Parameters
    ----------
    x : array (n_stims, n_times)
        Stimulus.
    y : array (n_times,)
        Dependent signal, time series to predict.
    trf_length : int
        Length of the TRF (in time samples).
    delta : scalar
        Step of the adjustment.
    nsegs : int
        Number of segments
    segno : int [0, nsegs-1]
        which segment to use for testing
    mindelta : scalar
        Smallest delta to use. If no improvement can be found in an iteration,
        the first step is to divide delta in half, but stop if delta becomes
        smaller than ``mindelta``.
    error : 'l2' | 'Sabs'
        Error function to use.
    return_history : bool
        Return error history as second return value.

    Returns
    -------
    history[best_iter] : None | array
        Winning kernel, or None if 0 is the best kernel.
    test_sse_history : list (only if ``return_history==True``)
        SSE for test data at each iteration.
    """
    assert x.ndim == 2
    assert y.shape == (x.shape[1],)

    # separate training and testing signal
    test_seg_len = int(floor(x.shape[1] / nsegs))
    test_index = slice(test_seg_len * segno, test_seg_len * (segno + 1))
    if segno == 0:
        train_index = (slice(test_seg_len, None),)
    elif segno == nsegs-1:
        train_index = (slice(0, -test_seg_len),)
    elif segno < 0 or segno >= nsegs:
        raise ValueError("segno=%r" % segno)
    else:
        train_index = (slice(0, test_seg_len * segno),
                       slice(test_seg_len * (segno + 1), None))

    y_train = tuple(y[..., i] for i in train_index)
    y_test = (y[..., test_index],)
    x_train = tuple(x[:, i] for i in train_index)
    x_test = (x[:, test_index],)

    return boost_segs(y_train, y_test, x_train, x_test, trf_length, delta,
                      mindelta, error, return_history)


def boost_segs(y_train, y_test, x_train, x_test, trf_length, delta, mindelta,
               error, return_history):
    """Boosting supporting multiple array segments

    Parameters
    ----------
    y_train, y_test : tuple of array (n_times,)
        Dependent signal, time series to predict.
    x_train, x_test : array (n_stims, n_times)
        Stimulus.
    trf_length : int
        Length of the TRF (in time samples).
    delta : scalar
        Step of the adjustment.
    mindelta : scalar
        Smallest delta to use. If no improvement can be found in an iteration,
        the first step is to divide delta in half, but stop if delta becomes
        smaller than ``mindelta``.
    error : str
        Error function to use.
    return_history : bool
        Return error history as second return value.

    Returns
    -------
    history[best_iter] : None | array
        Winning kernel, or None if 0 is the best kernel.
    test_sse_history : list (only if ``return_history==True``)
        SSE for test data at each iteration.
    """
    delta_error = DELTA_ERROR_FUNC[error]
    error = ERROR_FUNC[error]
    n_stims = len(x_train[0])
    if any(len(x) != n_stims for x in chain(x_train, x_test)):
        raise ValueError("Not all x have same number of stimuli")
    n_times = [len(y) for y in chain(y_train, y_test)]
    if any(x.shape[1] != n for x, n in izip(chain(x_train, x_test), n_times)):
        raise ValueError("y and x have inconsistent number of time points")

    h = np.zeros((n_stims, trf_length))

    # buffers
    y_train_error = tuple(y.copy() for y in y_train)
    y_test_error = tuple(y.copy() for y in y_test)

    ys_error = y_train_error + y_test_error
    xs = x_train + x_test

    new_error = np.empty(h.shape)
    new_sign = np.empty(h.shape, np.int8)

    # history lists
    history = []
    test_error_history = []
    # pre-assign iterators
    iter_h = tuple(product(xrange(h.shape[0]), xrange(h.shape[1])))
    iter_train_error = zip(y_train_error, x_train)
    iter_error = zip(ys_error, xs)
    for i_boost in xrange(999999):
        history.append(h.copy())

        # evaluate current h
        e_test = sum(error(y) for y in y_test_error)
        e_train = sum(error(y) for y in y_train_error)

        test_error_history.append(e_test)

        # stop the iteration if all the following requirements are met
        # 1. more than 10 iterations are done
        # 2. The testing error in the latest iteration is higher than that in
        #    the previous two iterations
        if (i_boost > 10 and e_test > test_error_history[-2] and
                e_test > test_error_history[-3]):
            # print("error(test) not improving in 2 steps")
            break

        # generate possible movements -> training error
        for i_stim, i_time in iter_h:
            # +/- delta
            e_add = e_sub = 0.
            for y_err, x in iter_train_error:
                e_add_, e_sub_ = delta_error(y_err, x[i_stim], delta, i_time)
                e_add += e_add_
                e_sub += e_sub_

            if e_add > e_sub:
                new_error[i_stim, i_time] = e_sub
                new_sign[i_stim, i_time] = -1
            else:
                new_error[i_stim, i_time] = e_add
                new_sign[i_stim, i_time] = 1

        i_stim, i_time = np.unravel_index(np.argmin(new_error), h.shape)
        new_train_error = new_error[i_stim, i_time]
        delta_signed = new_sign[i_stim, i_time] * delta

        # If no improvements can be found reduce delta
        if new_train_error > e_train:
            delta *= 0.5
            if delta >= mindelta:
                # print("new delta: %s" % delta)
                continue
            else:
                # print("No improvement possible for training data")
                break

        # update h with best movement
        h[i_stim, i_time] += delta_signed

        # abort if we're moving in circles
        if i_boost >= 2 and h[i_stim, i_time] == history[-2][i_stim, i_time]:
            # print("Same h after 2 iterations")
            break
        elif i_boost >= 3 and h[i_stim, i_time] == history[-3][i_stim, i_time]:
            # print("Same h after 3 iterations")
            break

        # update error
        for err, x in iter_error:
            update_error(err, x[i_stim], delta_signed, i_time)
    # else:
    #     print("maxiter exceeded")

    best_iter = np.argmin(test_error_history)
    # print('  (%i iterations)' % (i_boost + 1))

    if return_history:
        return history[best_iter] if best_iter else None, test_error_history
    else:
        return history[best_iter] if best_iter else None


def setup_workers(y, x, trf_length, delta, mindelta, nsegs, error):
    n_y, n_times = y.shape
    n_x, _ = x.shape

    y_buffer = RawArray('d', n_y * n_times)
    y_buffer[:] = y.ravel()
    x_buffer = RawArray('d', n_x * n_times)
    x_buffer[:] = x.ravel()

    job_queue = Queue(200)
    result_queue = Queue(200)

    args = (y_buffer, x_buffer, n_y, n_times, n_x, trf_length, delta,
            mindelta, nsegs, error, job_queue, result_queue)
    for _ in xrange(CONFIG['n_workers']):
        process = Process(target=boosting_worker, args=args)
        process.daemon = True
        process.start()

    return job_queue, result_queue


def boosting_worker(y_buffer, x_buffer, n_y, n_times, n_x, trf_length,
                    delta, mindelta, nsegs, error, job_queue, result_queue):
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    y = np.frombuffer(y_buffer, np.float64, n_y * n_times).reshape((n_y, n_times))
    x = np.frombuffer(x_buffer, np.float64, n_x * n_times).reshape((n_x, n_times))

    while True:
        y_i, seg_i = job_queue.get()
        if y_i == JOB_TERMINATE:
            return
        h = boost_1seg(x, y[y_i], trf_length, delta, nsegs, seg_i, mindelta,
                       error)
        result_queue.put((y_i, seg_i, h))


def put_jobs(queue, n_y, n_segs, stop):
    "Feed boosting jobs into a Queue"
    for job in product(xrange(n_y), xrange(n_segs)):
        queue.put(job)
        if stop.isSet():
            while not queue.empty():
                queue.get()
            break
    for _ in xrange(CONFIG['n_workers']):
        queue.put((JOB_TERMINATE, None))


def apply_kernel(x, h, out=None):
    """Predict ``y`` by applying kernel ``h`` to ``x``

    x.shape is (n_stims, n_samples)
    h.shape is (n_stims, n_trf_samples)
    """
    if out is None:
        out = np.zeros(x.shape[1])
    else:
        out.fill(0)

    for ind in xrange(len(h)):
        out += np.convolve(h[ind], x[ind])[:len(out)]

    return out


def evaluate_kernel(y, x, h, error):
    """Fit quality statistics

    Returns
    -------
    r : float | array
        Pearson correlation.
    rank_r : float | array
        Spearman rank correlation.
    error : float | array
        Error corresponding to error_func.
    """
    y_pred = apply_kernel(x, h)

    # discard onset (length of kernel)
    i0 = h.shape[-1] - 1
    y = y[..., i0:]
    y_pred = y_pred[..., i0:]

    error_func = ERROR_FUNC[error]
    return (np.corrcoef(y, y_pred)[0, 1],
            spearmanr(y, y_pred)[0],
            error_func(y - y_pred))
