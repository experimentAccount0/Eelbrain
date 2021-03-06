*********
Reference
*********

^^^^^^^^^^^^
Data Classes
^^^^^^^^^^^^

.. currentmodule:: eelbrain

Primary data classes:

.. autosummary::
   :toctree: generated

   Dataset
   Factor
   Var
   NDVar
   Datalist


Model classes (not usually initialized by themselves but through operations
on primary data-objects):

.. autosummary::
   :toctree: generated

   Interaction
   Model


NDVar dimensions (not usually initialized by themselves but through
:mod:`load` functions):

.. autosummary::
   :toctree: generated

   Case
   Categorial
   Scalar
   Sensor
   UTS


^^^^^^^^
File I/O
^^^^^^^^

Load
====

.. py:module:: load
.. py:currentmodule:: eelbrain

For convenient storage, Eelbrain objects can be
`pickled <https://docs.python.org/2/library/pickle.html>`_, although there is
no guarantee that objects can be exchanged across versions. Eelbrain's own
pickle I/O functions provide backwards compatibility:

.. autosummary::
   :toctree: generated

   load.unpickle
   load.update_subjects_dir


Functions for loading specific file formats as Eelbrain object:

.. autosummary::
   :toctree: generated

   load.wav

Modules:

.. autosummary::
   :toctree: generated

   load.eyelink
   load.fiff
   load.txt
   load.besa


Save
====

.. py:module:: save
.. py:currentmodule:: eelbrain

* `Pickling <http://docs.python.org/library/pickle.html>`_: All data-objects
  can be pickled. :func:`save.pickle` provides a shortcut for pickling objects.
* Text file export: Save a Dataset using its :py:meth:`~Dataset.save_txt`
  method. Save any iterator with :py:func:`save.txt`.

.. autosummary::
   :toctree: generated

   save.pickle
   save.txt
   save.wav


^^^^^^^^^^^^^^^^^^^^^^
Sorting and Reordering
^^^^^^^^^^^^^^^^^^^^^^

.. autosummary::
   :toctree: generated

   align
   align1
   Celltable
   choose
   combine
   shuffled_index


^^^^^^^^^^^^^^^^
NDVar Operations
^^^^^^^^^^^^^^^^

For the most common operations see :class:`NDVar` methods. Here are less common
and more specific operations:

.. autosummary::
   :toctree: generated

   Butterworth
   concatenate
   convolve
   cross_correlation
   cwt_morlet
   dss
   filter_data
   label_operator
   labels_from_clusters
   morph_source_space
   neighbor_correlation
   resample
   segment


^^^^^^^^^^^^^^^^^^^
Reverse Correlation
^^^^^^^^^^^^^^^^^^^

.. autosummary::
   :toctree: generated

   boosting
   BoostingResult


^^^^^^
Tables
^^^^^^

.. py:module:: table
.. py:currentmodule:: eelbrain

Manipulate data tables and compile information about data objects such as cell
frequencies:

.. autosummary::
   :toctree: generated

    table.difference
    table.frequencies
    table.melt
    table.melt_ndvar
    table.repmeas
    table.stats


^^^^^^^^^^
Statistics
^^^^^^^^^^

.. py:module:: test
.. py:currentmodule:: eelbrain

Univariate statistical tests:

.. autosummary::
   :toctree: generated
   
   test.TTest1Sample
   test.TTestRel
   test.anova
   test.pairwise
   test.ttest
   test.correlations
   test.lilliefors


^^^^^^^^^^^^^^^^^^^^^^^^^^
Mass-Univariate Statistics
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. py:module:: testnd
.. py:currentmodule:: eelbrain

.. autosummary::
   :toctree: generated

   testnd.ttest_1samp
   testnd.ttest_rel
   testnd.ttest_ind
   testnd.t_contrast_rel
   testnd.anova
   testnd.corr

By default the tests in this module produce maps of statistical parameters
along with maps of p-values uncorrected for multiple comparison. Using different
parameters, different methods for multiple comparison correction can be applied
(for more details and options see the documentation for individual tests):

**1: permutation for maximum statistic** (``samples=n``)
    Look for the maximum
    value of the test statistic in ``n`` permutations and calculate a p-value
    for each data point based on this distribution of maximum statistics.
**2: Threshold-based clusters** (``samples=n, pmin=p``)
    Find clusters of data
    points where the original statistic exceeds a value corresponding to an
    uncorrected p-value of ``p``. For each cluster, calculate the sum of the
    statistic values that are part of the cluster. Do the same in ``n``
    permutations of the original data and retain for each permutation the value
    of the largest cluster. Evaluate all cluster values in the original data
    against the distributiom of maximum cluster values (see [1]_).
**3: Threshold-free cluster enhancement** (``samples=n, tfce=True``)
    Similar to
    (1), but each statistical parameter map is first processed with the
    cluster-enhancement algorithm (see [2]_). This is the most computationally
    intensive option.


Two-stage tests
===============

Two-stage tests proceed by estimating parameters for a fixed effects model for
each subject, and then testing hypotheses on these parameter estimates on the
group level. Two-stage tests are implemented by fitting an :class:`~testnd.LM`
for each subject, and then combining them in a :class:`~testnd.LMGroup` to
retrieve coefficients for group level statistics.

.. autosummary::
   :toctree: generated

   testnd.LM
   testnd.LMGroup


References
==========

.. [1] Maris, E., & Oostenveld, R. (2007). Nonparametric
    statistical testing of EEG- and MEG-data. Journal of Neuroscience Methods,
    164(1), 177-190. `10.1016/j.jneumeth.2007.03.024
    <https://doi.org/10.1016/j.jneumeth.2007.03.024>`_
.. [2] Smith, S. M., and Nichols, T. E. (2009). Threshold-Free Cluster
    Enhancement: Addressing Problems of Smoothing, Threshold Dependence and
    Localisation in Cluster Inference. NeuroImage, 44(1), 83-98.
    `10.1016/j.neuroimage.2008.03.061
    <https://doi.org/10.1016/j.neuroimage.2008.03.061>`_


.. _ref-plotting:

^^^^^^^^
Plotting
^^^^^^^^

.. py:module:: plot
.. py:currentmodule:: eelbrain


Plot univariate data (:class:`Var` objects):

.. autosummary::
   :toctree: generated

   plot.Barplot
   plot.Boxplot
   plot.PairwiseLegend
   plot.Correlation
   plot.Histogram
   plot.Regression
   plot.Timeplot


Color tools for plotting:

.. autosummary::
   :toctree: generated

   plot.colors_for_categorial
   plot.colors_for_oneway
   plot.colors_for_twoway
   plot.ColorBar
   plot.ColorGrid
   plot.ColorList


Plot uniform time-series:

.. autosummary::
   :toctree: generated

   plot.UTS
   plot.UTSClusters
   plot.UTSStat


Plot multidimensional uniform time series:

.. autosummary::
   :toctree: generated

   plot.Array
   plot.Butterfly


Plot topographic maps of sensor space data:

.. autosummary::
   :toctree: generated

   plot.TopoArray
   plot.TopoButterfly
   plot.Topomap


Plot sensor layout maps:

.. autosummary::
   :toctree: generated

   plot.SensorMap
   plot.SensorMaps


Xax parameter
=============

Many plots have an ``Xax`` parameter which is used to sort the data in ``Y``
into different categories and plot them on separate axes. ``Xax`` can be
specified through categorial data, or as a dimension in ``Y``.

If a categorial data object is specified for ``Xax``, ``Y`` is split into the
categories in ``Xax``, and for every cell in ``Xax`` a separate subplot is
shown. For example, while

    >>> plot.Butterfly('meg', ds=ds)

will create a single Butterfly plot of the average response,

    >>> plot.Butterfly('meg', 'subject', ds=ds)

where ``'subject'`` is the ``Xax`` parameter, will create a separate subplot
for every subject with its average response.

A dimension on ``Y`` can be specified through a string starting with ``.``.
For example, to plot each case of ``meg`` separately, use::

   >>> plot.Butterfly('meg', '.case', ds=ds)


Layout
======

Most plots that also share certain layout keyword arguments. By default, all
those parameters are determined automatically, but individual values can be
specified manually by supplying them as keyword arguments.

h, w : scalar
   Height and width of the figure.
axh, axw : scalar
   Height and width of the axes.
nrow, ncol : None | int
   Limit number of rows/columns. If neither is specified, a square layout
   is produced
ax_aspect : scalar
   Width / height aspect of the axes.
name : str
   Window title (i.e. not displayed on the figure itself).

Plots that do take those parameters can be identified by the ``**layout`` in
their function signature.


GUI Interaction
===============

By default, new plots are automatically shown and, if the Python interpreter is
in interactive mode the GUI main loop is started. This behavior can be
controlled with 2 arguments when constructing a plot:

show : bool
    Show the figure in the GUI (default True). Use False for creating
    figures and saving them without displaying them on the screen.
run : bool
    Run the Eelbrain GUI app (default is True for interactive plotting and
    False in scripts).

The behavior can also be changed globally using :func:`configure`:


^^^^^^^^^^^^^^^
Plotting Brains
^^^^^^^^^^^^^^^

.. py:module:: plot.brain
.. py:currentmodule:: eelbrain

The :mod:`plot.brain` module contains specialized functions to plot
:class:`NDVar` objects containing source space data.
For this it uses a subclass of `PySurfer's
<https://pysurfer.github.io/#>`_ :class:`surfer.Brain` class.
The functions below allow quick plotting.
More specific control over the plots can be achieved through the
:class:`~plot._brain_object.Brain` object that is returned.

.. autosummary::
   :toctree: generated

    plot.brain.brain
    plot.brain.cluster
    plot.brain.dspm
    plot.brain.p_map
    plot.brain.annot
    plot.brain.annot_legend
    ~plot._brain_object.Brain

In order to make custom plots, a :class:`~plot._brain_object.Brain` figure
without any data added can be created with
``plot.brain.brain(ndvar.source, mask=False)``.

Surface options for plotting data on ``fsaverage``:

.. |surf_inflated| image:: images/brain_inflated.png
   :width: 200px
.. |surf_inflated_avg| image:: images/brain_inflated_avg.png
   :width: 200px
.. |surf_inflated_pre| image:: images/brain_inflated_pre.png
   :width: 200px
.. |surf_white| image:: images/brain_white.png
   :width: 200px
.. |surf_smoothwm| image:: images/brain_smoothwm.png
   :width: 200px
.. |surf_sphere| image:: images/brain_sphere.png
   :width: 200px

+---------------------+---------------------+---------------------+
| white               | smoothwm            | inflated_pre        |
|                     |                     |                     |
| |surf_white|        | |surf_smoothwm|     | |surf_inflated_pre| |
+---------------------+---------------------+---------------------+
| inflated            | inflated_avg        | sphere              |
|                     |                     |                     |
| |surf_inflated|     | |surf_inflated_avg| | |surf_sphere|       |
+---------------------+---------------------+---------------------+


.. _ref-guis:

^^^^
GUIs
^^^^

.. py:module:: gui
.. py:currentmodule:: eelbrain

Tools with a graphical user interface (GUI):

.. autosummary::
   :toctree: generated

    gui.select_components
    gui.select_epochs


.. _gui:

Controlling the GUI Application
===============================

Eelbrain uses a wxPython based application to create GUIs. This GUI appears as a
separate application with its own Dock icon. The way that control
of this GUI is managed depends on the environment form which it is invoked.

When Eelbrain plots are created from within iPython, the GUI is managed in the
background and control returns immediately to the terminal. There might be cases
in which this is not desired, for example when running scripts. After execution
of a script finishes, the interpreter is terminated and all associated plots are
closed. To avoid this, the command  ``gui.run(block=True)`` can be inserted at
the end of the script, which will keep all gui elements open until the user
quits the GUI application (see :func:`gui.run` below).

In interpreters other than iPython, input can not be processed from the GUI
and the interpreter shell at the same time. In that case, the GUI application
is activated by default whenever a GUI is created in interactive mode
(this can be avoided by passing ``run=False`` to any plotting function).
While the application is processing user input,
the shell can not be used. In order to return to the shell, quit the
application (the *python/Quit Eelbrain* menu command or Command-Q). In order to
return to the terminal without closing all windows, use the alternative
*Go/Yield to Terminal* command (Command-Alt-Q). To return to the application
from the shell, run :func:`gui.run`. Beware that if you terminate the Python
session from the terminal, the application is not given a chance to assure that
information in open windows is saved.

.. autosummary::
   :toctree: generated

    gui.run


^^^^^^^^^^^^^^
MNE-Experiment
^^^^^^^^^^^^^^

The :class:`MneExperiment` class serves as a base class for analyzing MEG
data (gradiometer only) with MNE:

.. autosummary::
   :toctree: generated

   MneExperiment

.. seealso::
    For the guide on working with the MneExperiment class see
    :ref:`experiment-class-guide`.


^^^^^^^^
Datasets
^^^^^^^^

.. py:module:: datasets
.. py:currentmodule:: eelbrain

Datasets for experimenting and testing:

.. autosummary::
    :toctree: generated

    datasets.get_loftus_masson_1994
    datasets.get_mne_sample
    datasets.get_uts
    datasets.get_uv


^^^^^^^^^^^^^
Configuration
^^^^^^^^^^^^^

.. autofunction:: configure
