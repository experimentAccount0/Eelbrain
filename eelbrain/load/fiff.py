'''
Tools for loading data from mne's fiff files.

.. autosummary::
   :toctree: generated

   events
   add_epochs
   add_mne_epochs
   epochs
   mne_epochs

Converting mne objects to :class:`NDVar`:

.. autosummary::
   :toctree: generated

   epochs_ndvar
   evoked_ndvar
   stc_ndvar


Managing events with a :class:`Dataset`
---------------------------------------

To load events as a :class:`~elbrain.data.Dataset`::

    >>> ds = load.fiff.events(path)

By default, the :class:`Dataset` contains a variable called ``"trigger"``
with trigger values, and a variable called ``"i_start"`` with the indices of
the events::

    >>> print ds[:10]
    trigger   i_start
    -----------------
    2         27977
    3         28345
    1         28771
    4         29219
    2         29652
    3         30025
    1         30450
    4         30839
    2         31240
    3         31665

These events can be modified in ``ds`` (adding variables, discarding events,
...) before being used to load data epochs. Epochs will be loaded based only
on the ``"i_start"`` variable.

Epochs can then be added to the :class:`Dataset` as an NDVar object with
:func:`add_epochs`::

    >>> ds2 = load.fiff.add_epochs(ds, -0.1, 0.6)

The returned ``ds2`` will contain the epochs as NDVar as ``ds['meg']``. If no
epochs got rejected during loading, ``ds2`` is identical with the input ``ds``.
If epochs were rejected, ``ds2`` is a shorter copy of the original ``ds``.

:class:`mne.Epochs` can be added to ``ds`` in the same fashion with::

    >>> ds = load.fiff.add_mne_epochs(ds, -0.1, 0.6)

The epochs can also be loaded as separate objects using::

    >>> epochs = load.fiff.epochs(ds)
    >>> mne_epochs = load.fiff.mne_epochs(ds)

Note that the returned epochs event does not contain meaningful event ids,
and ``epochs.event_id`` is None.

'''
from __future__ import division

import fnmatch
import os
from warnings import warn

import numpy as np

import mne
from mne.source_estimate import _BaseSourceEstimate
try:  # API change in 0.9 (mne.io module)
    from mne.io.constants import FIFF
    from mne import Evoked as _mne_Evoked
    from mne.io import Raw as _mne_Raw
    from mne import pick_types as _mne_pick_types
    from mne import pick_channels as _mne_pick_channels
    from mne.io import read_raw_kit as _mne_read_raw_kit
except ImportError:
    from mne.fiff import FIFF
    from mne.fiff import Evoked as _mne_Evoked
    from mne.fiff import Raw as _mne_Raw
    from mne.fiff import pick_types as _mne_pick_types
    from mne.fiff import pick_channels as _mne_pick_channels
    from mne.fiff.kit import read_raw_kit as _mne_read_raw_kit

from .. import _colorspaces as _cs
from .._utils import ui
from .._data_obj import Var, NDVar, Dataset, Sensor, SourceSpace, UTS


def mne_raw(path=None, proj=False, **kwargs):
    """
    Returns a mne Raw object with added projections if appropriate.

    Parameters
    ----------
    path : None | str(path)
        path to the raw fiff file. If ``None``, a file can be chosen form a
        file dialog.
    proj : bool | str(path)
        Add projections from a separate file to the Raw object.
        **``False``**: No proj file will be added.
        **``True``**: ``'{raw}*proj.fif'`` will be used.
        ``'{raw}'`` will be replaced with the raw file's path minus '_raw.fif',
        and '*' will be expanded using fnmatch. If multiple files match the
        pattern, a ValueError will be raised.
        **``str``**: A custom path template can be provided, ``'{raw}'`` and
        ``'*'`` will be treated as with ``True``.
    kwargs
        Additional keyword arguments are forwarded to mne Raw initialization.

    """
    if path is None:
        path = ui.ask_file("Pick a Raw Fiff File", "Pick a Raw Fiff File",
                           [('Functional image file (*.fif)', '*.fif'),
                            ('KIT Raw File (*.sqd,*.con', '*.sqd;*.con')])
        if not path:
            return

    if not os.path.isfile(path):
        raise IOError("%r is not a file" % path)

    if isinstance(path, basestring):
        _, ext = os.path.splitext(path)
        if ext.startswith('.fif'):
            raw = _mne_Raw(path, **kwargs)
        elif ext in ('.sqd', '.con'):
            raw = _mne_read_raw_kit(path, **kwargs)
        else:
            raise ValueError("Unknown extension: %r" % ext)
    else:
        raw = _mne_Raw(path, **kwargs)

    if proj:
        if proj == True:
            proj = '{raw}*proj.fif'

        if '{raw}' in proj:
            raw_file = raw.info['filename']
            raw_root, _ = os.path.splitext(raw_file)
            raw_root = raw_root.rstrip('raw')
            proj = proj.format(raw=raw_root)

        if '*' in proj:
            head, tail = os.path.split(proj)
            names = fnmatch.filter(os.listdir(head), tail)
            if len(names) == 1:
                proj = os.path.join(head, names[0])
            else:
                if len(names) == 0:
                    err = "No file matching %r"
                else:
                    err = "Multiple files matching %r"
                raise ValueError(err % proj)

        # add the projections to the raw file
        proj = mne.read_proj(proj)
        raw.add_proj(proj, remove_existing=True)

    return raw


def events(raw=None, merge=-1, proj=False, name=None,
           bads=None, stim_channel=None, **kwargs):
    """
    Load events from a raw fiff file.

    Use :func:`fiff_epochs` to load MEG data corresponding to those events.

    Parameters
    ----------
    raw : str(path) | None | mne Raw
        The raw fiff file from which to extract events (if ``None``, a file
        dialog will be displayed).
    merge : int
        Merge steps occurring in neighboring samples. The integer value
        indicates over how many samples events should be merged, and the sign
        indicates in which direction they should be merged (negative means
        towards the earlier event, positive towards the later event).
    proj : bool | str
        Path to the projections file that will be loaded with the raw file.
        ``'{raw}'`` will be expanded to the raw file's path minus extension.
        With ``proj=True``, ``'{raw}_*proj.fif'`` will be used,
        looking for any projection file starting with the raw file's name.
        If multiple files match the pattern, a ValueError will be raised.
    name : str | None
        A name for the Dataset. If ``None``, the raw filename will be used.
    bads : None | list
        Specify additional bad channels in the raw data file (these are added
        to the ones that are already defined in the raw file).
    stim_channel : None | string | list of string
        Name of the stim channel or all the stim channels
        affected by the trigger. If None, the config variables
        'MNE_STIM_CHANNEL', 'MNE_STIM_CHANNEL_1', 'MNE_STIM_CHANNEL_2',
        etc. are read. If these are not found, it will default to
        'STI 014'.
    others :
        Keyword arguments for loading the raw file.

    Returns
    -------
    events : Dataset
        A Dataset with the following variables:
         - *i_start*: the index of the event in the raw file.
         - *trigger*: the event value.
        The Dataset's info dictionary contains the following values:
         - *raw*: the mne Raw object.

    """
    if raw is None or isinstance(raw, basestring):
        raw = mne_raw(raw, proj=proj, **kwargs)

    if bads is not None:
        raw.info['bads'].extend(bads)

    if name is None:
        raw_path = raw.info['filename']
        if isinstance(raw_path, basestring):
            name = os.path.basename(raw_path)
        else:
            name = None

    # stim_channel_bl: see commit 52796ad1267b5ad4fba10f6ca5f2b7cfba65ba9b or earlier
    evts = mne.find_stim_steps(raw, merge=merge, stim_channel=stim_channel)
    idx = np.nonzero(evts[:, 2])
    evts = evts[idx]

    if len(evts) == 0:
        raise ValueError("No events found!")

    i_start = Var(evts[:, 0], name='i_start')
    trigger = Var(evts[:, 2], name='trigger')
    info = {'raw': raw}
    return Dataset(trigger, i_start, name=name, info=info)


def _guess_ndvar_data_type(info):
    """Guess which type of data to extract from an mne object.

    Checks for the presence of channels in that order: "mag", "eeg", "grad".
    If none are found, a ValueError is raised.

    Parameters
    ----------
    info : dict
        MNE info dictionary.

    Returns
    -------
    data : str
        Kind of data to extract
    """
    for ch in info['chs']:
        kind = ch['kind']
        if kind == FIFF.FIFFV_MEG_CH:
            if ch['unit'] == FIFF.FIFF_UNIT_T_M:
                return 'grad'
            elif ch['unit'] == FIFF.FIFF_UNIT_T:
                return 'mag'
        elif kind == FIFF.FIFFV_EEG_CH:
            return 'eeg'
    raise ValueError("No MEG or EEG channel found in info.")


def _ndvar_epochs_picks(info, data, exclude):
    if data == 'eeg':
        meg = False
        eeg = True
    elif data in ['grad', 'mag']:
        meg = data
        eeg = False
    else:
        err = "data=%r (needs to be 'eeg', 'grad' or 'mag')" % data
        raise ValueError(err)
    picks = _mne_pick_types(info, meg=meg, eeg=eeg, stim=False, exclude=exclude)
    return picks


def _ndvar_epochs_reject(data, reject):
    if reject:
        if not np.isscalar(reject):
            err = ("Reject must be scalar (rejection threshold); got %s." %
                   repr(reject))
            raise ValueError(err)
        reject = {data: reject}
    else:
        reject = None
    return reject


def epochs(ds, tmin=-0.1, tmax=0.6, baseline=None, decim=1, mult=1, proj=False,
           data='mag', reject=None, exclude='bads', info=None, name=None,
           raw=None, sensors=None, i_start='i_start'):
    """
    Load epochs as :class:`NDVar`.

    Parameters
    ----------
    ds : Dataset
        Dataset containing a variable which defines epoch cues (i_start).
    tmin, tmax : scalar
        First and last sample to include in the epochs in seconds.
    baseline : tuple(tmin, tmax) | ``None``
        Time interval for baseline correction. Tmin/tmax in seconds, or None to
        use all the data (e.g., ``(None, 0)`` uses all the data from the
        beginning of the epoch up to t=0). ``baseline=None`` for no baseline
        correction (default).
    decim : int
        Downsample the data by this factor when importing. ``1`` means no
        downsampling. Note that this function does not low-pass filter
        the data. The data is downsampled by picking out every
        n-th sample (see `Wikipedia <http://en.wikipedia.org/wiki/Downsampling>`_).
    mult : scalar
        multiply all data by a constant.
    proj : bool
        mne.Epochs kwarg (subtract projections when loading data)
    data : 'eeg' | 'mag' | 'grad'
        The kind of data to load.
    reject : None | scalar
        Threshold for rejecting epochs (peak to peak). Requires a for of
        mne-python which implements the Epochs.model['index'] variable.
    exclude : list of string | str
        Channels to exclude (:func:`mne.pick_types` kwarg).
        If 'bads' (default), exclude channels in info['bads'].
        If empty do not exclude any.
    info : None | dict
        Entries for the ndvar's info dict.
    name : str
        name for the new NDVar.
    raw : None | mne Raw
        Raw file providing the data; if ``None``, ``ds.info['raw']`` is used.
    sensors : None | Sensor
        The default (``None``) reads the sensor locations from the fiff file.
        If the fiff file contains incorrect sensor locations, a different
        Sensor instance can be supplied through this kwarg.
    i_start : str
        name of the variable containing the index of the events.

    Returns
    -------
    epochs : NDVar
        The epochs as NDVar object.
    """
    if raw is None:
        raw = ds.info['raw']

    picks = _ndvar_epochs_picks(raw.info, data, exclude)
    reject = _ndvar_epochs_reject(data, reject)

    epochs_ = mne_epochs(ds, tmin, tmax, baseline, i_start, raw, decim=decim,
                         picks=picks, reject=reject, proj=proj)
    ndvar = epochs_ndvar(epochs_, name, data, mult=mult, info=info,
                         sensors=sensors)

    if len(epochs_) == 0:
        raise RuntimeError("No events left in %r" % raw.info['filename'])
    return ndvar


def add_epochs(ds, tmin=-0.1, tmax=0.6, baseline=None, decim=1, mult=1,
               proj=False, data='mag', reject=None, exclude='bads', info=None,
               name="meg", raw=None, sensors=None, i_start='i_start',
               **kwargs):
    """
    Load epochs and add them to a dataset as :class:`NDVar`.

    Unless the ``reject`` argument is specified, ``ds``
    is modified in place. With ``reject``, a subset of ``ds`` is returned
    containing only those events for which data was loaded.

    Parameters
    ----------
    ds : Dataset
        Dataset containing a variable which defines epoch cues (i_start) and to
        which the epochs are added.
    tmin, tmax : scalar
        First and last sample to include in the epochs in seconds.
    baseline : tuple(tmin, tmax) | ``None``
        Time interval for baseline correction. Tmin/tmax in seconds, or None to
        use all the data (e.g., ``(None, 0)`` uses all the data from the
        beginning of the epoch up to t=0). ``baseline=None`` for no baseline
        correction (default).
    decim : int
        Downsample the data by this factor when importing. ``1`` means no
        downsampling. Note that this function does not low-pass filter
        the data. The data is downsampled by picking out every
        n-th sample (see `Wikipedia <http://en.wikipedia.org/wiki/Downsampling>`_).
    mult : scalar
        multiply all data by a constant.
    proj : bool
        mne.Epochs kwarg (subtract projections when loading data)
    data : 'eeg' | 'mag' | 'grad'
        The kind of data to load.
    reject : None | scalar
        Threshold for rejecting epochs (peak to peak). Requires a for of
        mne-python which implements the Epochs.model['index'] variable.
    exclude : list of string | str
        Channels to exclude (:func:`mne.pick_types` kwarg).
        If 'bads' (default), exclude channels in info['bads'].
        If empty do not exclude any.
    info : None | dict
        Entries for the ndvar's info dict.
    name : str
        name for the new NDVar.
    raw : None | mne Raw
        Raw file providing the data; if ``None``, ``ds.info['raw']`` is used.
    sensors : None | Sensor
        The default (``None``) reads the sensor locations from the fiff file.
        If the fiff file contains incorrect sensor locations, a different
        Sensor instance can be supplied through this kwarg.
    i_start : str
        name of the variable containing the index of the events.

    Returns
    -------
    ds : Dataset
        Dataset containing the epochs. If no events are rejected, ``ds`` is the
        same object as the input ``ds`` argument, otherwise a copy of it.
    """
    if 'target' in kwargs:
        warn("load.fiff.add_epochs(): target kwarg is deprecated; use name "
             "instead.", DeprecationWarning)
        name = kwargs.pop('target')
    if kwargs:
        raise RuntimeError("Unknown parameters: %s" % str(kwargs.keys()))

    if raw is None:
        raw = ds.info['raw']

    picks = _ndvar_epochs_picks(raw.info, data, exclude)
    reject = _ndvar_epochs_reject(data, reject)

    epochs_ = mne_epochs(ds, tmin, tmax, baseline, i_start, raw, decim=decim,
                         picks=picks, reject=reject, proj=proj, preload=True)
    ds = _trim_ds(ds, epochs_)
    ds[name] = epochs_ndvar(epochs_, name, data, mult=mult, info=info,
                            sensors=sensors)
    return ds


def add_mne_epochs(ds, tmin=-0.1, tmax=0.6, baseline=None, target='epochs',
                   **kwargs):
    """
    Load epochs and add them to a dataset as :class:`mne.Epochs`.

    If, after loading, the Epochs contain fewer cases than the Dataset, a copy
    of the Dataset is made containing only those events also contained in the
    Epochs. Note that the Epochs are always loaded with ``preload==True``.


    Parameters
    ----------
    ds : Dataset
        Dataset with events from a raw fiff file (i.e., created by
        load.fiff.events).
    tmin, tmax : scalar
        First and last sample to include in the epochs in seconds.
    baseline : tuple(tmin, tmax) | ``None``
        Time interval for baseline correction. Tmin/tmax in seconds, or None to
        use all the data (e.g., ``(None, 0)`` uses all the data from the
        beginning of the epoch up to t=0). ``baseline=None`` for no baseline
        correction (default).
    target : str
        Name for the Epochs object in the Dataset.
    kwargs :
        Any additional keyword arguments are forwarded to the mne Epochs
        object initialization.

    """
    kwargs['preload'] = True
    epochs_ = mne_epochs(ds, tmin, tmax, baseline, **kwargs)
    ds = _trim_ds(ds, epochs_)
    ds[target] = epochs_
    return ds


def _mne_events(ds=None, i_start='i_start', trigger='trigger'):
    """
    Convert events from a Dataset into mne events.
    """
    if isinstance(i_start, basestring):
        i_start = ds[i_start]

    N = len(i_start)

    if isinstance(trigger, basestring):
        trigger = ds[trigger]
    elif trigger is None:
        trigger = np.ones(N)

    events = np.empty((N, 3), dtype=np.int32)
    events[:, 0] = i_start.x
    events[:, 1] = 0
    events[:, 2] = trigger
    return events


def mne_epochs(ds, tmin=-0.1, tmax=0.6, baseline=None, i_start='i_start',
               raw=None, drop_bad_chs=True, **kwargs):
    """
    Load epochs as :class:`mne.Epochs`.

    Parameters
    ----------
    ds : Dataset
        Dataset containing a variable which defines epoch cues (i_start).
    tmin, tmax : scalar
        First and last sample to include in the epochs in seconds.
    baseline : tuple(tmin, tmax) | ``None``
        Time interval for baseline correction. Tmin/tmax in seconds, or None to
        use all the data (e.g., ``(None, 0)`` uses all the data from the
        beginning of the epoch up to t=0). ``baseline=None`` for no baseline
        correction (default).
    i_start : str
        name of the variable containing the index of the events.
    raw : None | mne Raw
        If None, ds.info['raw'] is used.
    drop_bad_chs : bool
        Drop all channels in raw.info['bads'] form the Epochs. This argument is
        ignored if the picks argument is specified.
    kwargs
        :class:`mne.Epochs` parameters.
    """
    if raw is None:
        raw = ds.info['raw']

    if drop_bad_chs and ('picks' not in kwargs) and raw.info['bads']:
        kwargs['picks'] = _mne_pick_channels(raw.info['ch_names'], [],
                                             raw.info['bads'])

    events = _mne_events(ds=ds, i_start=i_start)
    # epochs with (event_id == None) does not use columns 1 and 2 of events
    events[:, 1] = np.arange(len(events))
    epochs = mne.Epochs(raw, events, None, tmin, tmax, baseline, **kwargs)
    return epochs


def mne_Epochs(*args, **kwargs):
    warn("load.fiff.mne_Epochs() is deprecated; use load.fiff.mne_epochs "
         "instead", DeprecationWarning)

    if 'tstart' in kwargs:
        warn("load.fiff.mne_epochs(): tstart argument is deprecated. Use tmin "
             "instead", DeprecationWarning)
        kwargs['tmin'] = kwargs.pop('tstart')
    elif not 'tmin' in kwargs:
        kwargs['tmin'] = -0.1
    if 'tstop' in kwargs:
        warn("load.fiff.mne_epochs(): tstop argument is deprecated. Use tmax "
             "instead", DeprecationWarning)
        kwargs['tmax'] = kwargs.pop('tstop')
    elif not 'tmax' in kwargs:
        kwargs['tmax'] = 0.5
    return mne_epochs(*args, **kwargs)


def sensor_dim(fiff, picks=None, sysname='fiff-sensors'):
    """
    Create a Sensor dimension object based on the info in a fiff object.

    Parameters
    ----------
    fiff : mne-python object
        Object that has a .info attribute that contains measurement info.
    picks : None | array of int
        Channel picks (as used in mne-python). If None (default) all channels
        are included.
    sysname : str
        Name of the sensor system (stored as Sensor attribute).

    Returns
    -------
    sensor_dim : Sensor
        Sensor dimension object.
    """
    info = fiff.info
    if picks is None:
        chs = info['chs']
    else:
        chs = [info['chs'][i] for i in picks]

    ch_locs = []
    ch_names = []
    for ch in chs:
        x, y, z = ch['loc'][:3]
        ch_name = ch['ch_name']
        ch_locs.append((x, y, z))
        ch_names.append(ch_name)
    return Sensor(ch_locs, ch_names, sysname=sysname)


def epochs_ndvar(epochs, name='meg', data='mag', exclude='bads', mult=1,
                 info=None, sensors=None, vmax=None):
    """
    Convert an :class:`mne.Epochs` object to an :class:`NDVar`.

    Parameters
    ----------
    epochs : mne.Epochs
        The epochs object
    name : None | str
        Name for the NDVar.
    data : 'eeg' | 'mag' | 'grad' | None
        The kind of data to include. If None, guess based on ``epochs.info``.
    exclude : list of string | str
        Channels to exclude (:func:`mne.pick_types` kwarg).
        If 'bads' (default), exclude channels in info['bads'].
        If empty do not exclude any.
    mult : scalar
        multiply all data by a constant.
    info : None | dict
        Additional contents for the info dictionary of the NDVar.
    sensors : None | Sensor
        The default (``None``) reads the sensor locations from the fiff file.
        If the fiff file contains incorrect sensor locations, a different
        Sensor can be supplied through this kwarg.
    vmax : None | scalar
        Set a default range for plotting.
    """
    if data is None:
        data = _guess_ndvar_data_type(epochs.info)

    if data == 'eeg':
        info_ = _cs.eeg_info(vmax, mult)
        summary_vmax = 0.1 * vmax if vmax else None
        summary_info = _cs.eeg_info(summary_vmax, mult)
    elif data == 'mag':
        info_ = _cs.meg_info(vmax, mult)
        summary_vmax = 0.1 * vmax if vmax else None
        summary_info = _cs.meg_info(summary_vmax, mult)
    elif data == 'grad':
        info_ = _cs.meg_info(vmax, mult, 'T/cm')
        summary_vmax = 0.1 * vmax if vmax else None
        summary_info = _cs.meg_info(summary_vmax, mult, 'T/cm')
    else:
        raise ValueError("data=%r" % data)
    info_.update(proj='z root', samplingrate=epochs.info['sfreq'],
                 summary_info=summary_info)
    if info:
        info_.update(info)

    x = epochs.get_data()
    picks = _ndvar_epochs_picks(epochs.info, data, exclude)
    if len(picks) < x.shape[1]:
        x = x[:, picks]

    if mult != 1:
        x *= mult

    sensor = sensors or sensor_dim(epochs, picks=picks)
    time = UTS(epochs.tmin, 1. / epochs.info['sfreq'], len(epochs.times))
    return NDVar(x, ('case', sensor, time), info=info_, name=name)


def evoked_ndvar(evoked, name='meg', data='mag', exclude='bads', vmax=None):
    """
    Convert one or more mne :class:`Evoked` objects to an :class:`NDVar`.

    Parameters
    ----------
    evoked : str | Evoked | list of Evoked
        The Evoked to convert to NDVar. Can be a string designating a file
        path to a evoked fiff file containing only one evoked.
    name : str
        Name of the NDVar.
    data : 'eeg' | 'mag' | 'grad'
        The kind of data to include.
    exclude : list of string | string
        Channels to exclude (:func:`mne.pick_types` kwarg).
        If 'bads' (default), exclude channels in info['bads'].
        If empty do not exclude any.
    vmax : None | scalar
        Set a default range for plotting.

    Notes
    -----
    If evoked objects have different channels, the intersection is used (i.e.,
    only the channels present in all objects are retained).
    """
    if isinstance(evoked, basestring):
        evoked = _mne_Evoked(evoked)

    if isinstance(evoked, _mne_Evoked):
        picks = _ndvar_epochs_picks(evoked.info, data, exclude)

        x = evoked.data[picks]
        sensor = sensor_dim(evoked, picks=picks)
        time = UTS.from_int(evoked.first, evoked.last, evoked.info['sfreq'])
        dims = (sensor, time)
    else:
        e0 = evoked[0]

        # find common channels
        all_chs = set(e0.info['ch_names'])
        exclude = set(e0.info['bads'])
        times = e0.times
        for e in evoked[1:]:
            chs = set(e.info['ch_names'])
            all_chs.update(chs)
            exclude.update(e.info['bads'])
            missing = all_chs.difference(chs)
            exclude.update(missing)
            if not np.all(e.times == times):
                raise ValueError("Not all evoked have the same time points.")

        # get data
        x = []
        sensor = None
        exclude = list(exclude)
        for e in evoked:
            picks = _ndvar_epochs_picks(e.info, data, exclude)
            x.append(e.data[picks])
            if sensor is None:
                sensor = sensor_dim(e, picks=picks)

        time = UTS.from_int(e0.first, e0.last, e0.info['sfreq'])
        dims = ('case', sensor, time)

    info = _cs.meg_info(vmax)
    return NDVar(x, dims, info=info, name=name)


def stc_ndvar(stc, subject, src, subjects_dir=None, name=None, check=True,
              parc='aparc'):
    """
    Convert one or more :class:`mne.SourceEstimate` objects to an :class:`NDVar`.

    Parameters
    ----------
    stc : SourceEstimate | list of SourceEstimates | str
        The source estimate object(s) or a path to an stc file.
    subject : str
        MRI subject (used for loading MRI in PySurfer plotting)
    src : str
        The kind of source space used (e.g., 'ico-4').
    subjects_dir : None | str
        The path to the subjects_dir (needed to locate the source space
        file).
    name : str | None
        Ndvar name.
    check : bool
        If multiple stcs are provided, check if all stcs have the same times
        and vertices.
    parc : None | str
        Parcellation to add to the source space.
    """
    subjects_dir = mne.utils.get_subjects_dir(subjects_dir)

    if isinstance(stc, basestring):
        stc = mne.read_source_estimate(stc)

    # construct data array
    if isinstance(stc, _BaseSourceEstimate):
        case = False
        x = stc.data
    else:
        case = True
        stcs = stc
        stc = stcs[0]
        if check:
            times = stc.times
            vertno = stc.vertno
            for stc_ in stcs[1:]:
                assert np.array_equal(stc_.times, times)
                assert np.array_equal(stc_.vertno, vertno)
        x = np.array([s.data for s in stcs])

    # Construct NDVar Dimensions
    time = UTS(stc.tmin, stc.tstep, stc.shape[1])
    if isinstance(stc, mne.VolSourceEstimate):
        ss = SourceSpace([stc.vertno], subject, src, subjects_dir, parc)
    else:
        ss = SourceSpace(stc.vertno, subject, src, subjects_dir, parc)

    if case:
        dims = ('case', ss, time)
    else:
        dims = (ss, time)

    return NDVar(x, dims, name=name)


def _trim_ds(ds, epochs):
    """
    Trim a Dataset to account for rejected epochs. If no epochs were rejected,
    the original ds is rturned.

    Parameters
    ----------
    ds : Dataset
        Dataset that was used to construct epochs.
    epochs : Epochs
        Epochs loaded with mne_epochs()
    """
    if len(epochs) < ds.n_cases:
        index = epochs.events[:, 1]
        ds = ds.sub(index)

    return ds