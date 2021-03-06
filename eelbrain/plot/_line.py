# -*- coding: utf-8 -*-
# Author: Christian Brodbeck <christianbrodbeck@nyu.edu>
"Line plots"
from __future__ import division

from itertools import cycle, izip, repeat

import numpy as np

from .._data_obj import ascategorial, asndvar, assub
from ._base import (
    EelFigure, Layout, LegendMixin, XAxisMixin, find_axis_params_data,
    frame_title)


class LineStack(LegendMixin, XAxisMixin, EelFigure):
    u"""Stack multiple lines vertically
    
    Parameters
    ----------
    y : NDVar
        Values to plot.
    x : cateorial
        Variable to aggregate cases into lines (default is to plot each line).
    sub : None | index array
        Only use a subset of the data provided.
    ds : None | Dataset
        If a Dataset is specified, all data-objects can be specified as
        names of Dataset variables.
    offset : float | str
        The distance between the baseline (y = 0) for the different lines. 
        Can be a string expressed as a function of y. For example, 
        ``'0.66 * max(y)'`` will offset each line by 0.66 times the maximum 
        value in ``y`` (after aggregating if ``x`` is specified). The default is
        ``'2/3 * max(y.max(), -y.min())'``.
    xlim : tuple of 2 scalar
        Initial x-axis display limits.
    xlabel : bool | str
        X-axis label. By default the label is inferred from the data.
    xticklabels : bool
        Print x-axis tick-labels (set to False to suppress them).
    ylabel : bool | str
        Y-axis label. By default the label is inferred from the data.
    colors : dict | sequence of colors
        Colors for the lines (default is all lines in black).
    ylabels : bool | dict | sequence of str
        Labels for the different lines, placed along the y-axis.
    legend : str | int | 'fig' | None
        Matplotlib figure legend location argument or 'fig' to plot the
        legend in a separate figure.
    clip : bool
        Clip lines outside of axes (default ``True``).
        
    Notes
    -----
    Navigation:
     - ``←``: scroll left
     - ``→``: scroll right
     - ``home``: scroll to beginning
     - ``end``: scroll to end
     - ``f``: x-axis zoom in (reduce x axis range)
     - ``d``: x-axis zoom out (increase x axis range)
    """
    _name = "LineStack"

    def __init__(self, y, x=None, sub=None, ds=None, offset='y.max() - y.min()',
                 ylim=None, xlim=None, xlabel=True, xticklabels=True,
                 ylabel=True, order=None, colors=None, ylabels=True, xdim=None,
                 legend=None, clip=True, *args, **kwargs):
        sub = assub(sub, ds)
        if isinstance(y, (tuple, list)):
            if x is not None:
                raise TypeError(
                    "x can only be used to divide y into different lines if y "
                    "is a single NDVar (got y=%r)." % (y,))
            elif order is not None:
                raise TypeError("The order parameter only applies if y is a "
                                "single NDVar")
            ys = tuple(asndvar(y_, sub, ds) for y_ in y)
            xdims = set(y_.get_dimnames((None,))[0] for y_ in ys)
            if len(xdims) > 1:
                raise ValueError("NDVars must have same dimension, got %s" %
                                 (tuple(xdims),))
            xdim = xdims.pop()
            ydata = tuple(y_.get_data(xdim) for y_ in ys)
            ny = len(ydata)
            xdim_objs = tuple(y_.get_dim(xdim) for y_ in ys)
            xdata = tuple(d._axis_data() for d in xdim_objs)
            xdim_obj = reduce(lambda d1, d2: d1._union(d2), xdim_objs)

            if isinstance(offset, basestring):
                offset = max(eval(offset, {'y': y_}) for y_ in ydata)

            cells = cell_labels = tuple(y_.name for y_ in ys)

            if ylabel is True:
                _, ylabel = find_axis_params_data(ys[0], ylabel)
            epochs = (ys,)
        else:
            y = asndvar(y, sub, ds)
            if x is not None:
                x = ascategorial(x, sub, ds)
                y = y.aggregate(x)
            # find plotting dims
            if xdim is None and y.has_dim('time'):
                ydim, xdim = y.get_dimnames((None, 'time'))
            else:
                ydim, xdim = y.get_dimnames((None, xdim))
            xdim_obj = y.get_dim(xdim)

            # get data
            ydata = y.get_data((ydim, xdim))

            if isinstance(offset, basestring):
                offset = eval(offset, {'y': y})

            # find cells
            if x is None:
                cells = y.get_dim(ydim)
                cell_labels = map(str, cells)
            else:
                cells = cell_labels = x.cells

            if order is not None:
                sort_index = [cells._array_index(i) for i in order]
                ydata = ydata[sort_index]
                cells = tuple(cells[i] for i in sort_index)
                cell_labels = tuple(cell_labels[i] for i in sort_index)

            if ylabel is True:
                _, ylabel = find_axis_params_data(y, ylabel)
            epochs = ((y,),)

            ny = len(ydata)
            xdata = repeat(xdim_obj._axis_data(), ny)

        offsets = np.arange(ny - 1, -1, -1) * offset

        if ylabels is True:
            ylabels = cell_labels

        # colors
        if colors is None:
            color_iter = repeat('k', ny)
        elif isinstance(colors, dict):
            color_iter = (colors[cell] for cell in cells)
        elif len(colors) < ny:
            color_iter = cycle(colors)
        else:
            color_iter = colors

        layout = Layout(1, 0.5, 6, *args, **kwargs)
        EelFigure.__init__(self, frame_title(y, x), layout)
        ax = self._axes[0]

        handles = [ax.plot(x_, y_ + offset_, color=color, clip_on=clip)[0] for
                   x_, y_, offset_, color in
                   izip(xdata, ydata, offsets, color_iter)]

        if ylim is None:
            ymin = ydata.min()
            ylim = (ydata[0].min(), offset * ny)
        else:
            ymin, ymax = ylim
            ylim = (ymin, offset * (ny - 1) + ymax)

        ax.grid(True)
        ax.set_frame_on(False)
        ax.xaxis.set_ticks_position('none')
        ax.yaxis.set_ticks_position('none')
        ax.set_yticks(offsets)
        ax.set_yticklabels(ylabels or (), va='center' if ymin < 0 else 'baseline')
        ax.set_ylim(ylim)
        self._configure_xaxis_dim(xdim_obj, xlabel, xticklabels)
        if ylabel:
            ax.set_ylabel(ylabel)
        XAxisMixin.__init__(self, epochs, xdim, xlim)
        LegendMixin.__init__(self, legend, dict(izip(cell_labels, handles)))
        self._show()
