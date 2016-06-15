from __future__ import division

import numpy as np

import nengo.utils.numpy as npext
from nengo.exceptions import SignalError
from nengo.utils.compat import StringIO, is_integer


class Signal(object):
    """Represents data or views onto data within a Nengo simulation.

    Signals are tightly coupled to NumPy arrays, which is how live data is
    represented in a Nengo simulation. Signals provide a view onto the
    important metadata of the live NumPy array, and maintain the original
    value of the array in order to reset the simulation to the initial state.

    Parameters
    ----------
    initial_value : array_like
        The initial value of the signal. Much of the metadata tracked by the
        Signal is based on this array as well (e.g., dtype).
    name : str, optional (Default: None)
        Name of the signal. Primarily used for debugging.
        If None, the memory location of the Signal will be used.
    base : Signal, optional (Default: None)
        The base signal, if this signal is a view on another signal.
        Linking the two signals with the ``base`` argument is necessary
        to ensure that their live data is also linked.
    readonly : bool, optional (Default: False)
        Whether this signal and its related live data should be marked as
        readonly. Writing to these arrays will raise an exception.
    """

    # Set assert_named_signals True to raise an Exception
    # if model.signal is used to create a signal with no name.
    # This can help to identify code that's creating un-named signals,
    # if you are trying to track down mystery signals that are showing
    # up in a model.
    assert_named_signals = False

    def __init__(self, initial_value, name=None, base=None, readonly=False):
        self._initial_value = np.asarray(initial_value).view()
        self._initial_value.setflags(write=False)

        if base is not None:
            assert isinstance(base, Signal) and not base.is_view
            # make sure initial_value uses the same data as base.initial_value
            assert (npext.array_base(initial_value) is
                    npext.array_base(base.initial_value))
        self._base = base

        if self.assert_named_signals:
            assert name
        self._name = name

        self._readonly = bool(readonly)

    def __getitem__(self, item):
        """Index or slice into array"""
        if not isinstance(item, tuple):
            item = (item,)

        if not all(is_integer(i) or isinstance(i, slice) for i in item):
            raise SignalError("Can only index or slice into signals")

        if all(map(is_integer, item)):
            # turn one index into slice to get a view from numpy
            item = item[:-1] + (slice(item[-1], item[-1]+1),)

        return Signal(self._initial_value[item],
                      name="%s[%s]" % (self.name, item),
                      base=self.base)

    def __repr__(self):
        return "Signal(%s, shape=%s)" % (self._name, self.shape)

    @property
    def base(self):
        """(Signal or None) The base signal, if this signal is a view.

        Linking the two signals with the ``base`` argument is necessary
        to ensure that their live data is also linked.
        """
        return self if self._base is None else self._base

    @property
    def dtype(self):
        """(numpy.dtype) Data type of the signal (e.g., float64)."""
        return self.initial_value.dtype

    @property
    def elemoffset(self):
        """(int) Offset of data from base in elements."""
        return self.offset // self.itemsize

    @property
    def elemstrides(self):
        """(int) Strides of data in elements."""
        return tuple(s // self.itemsize for s in self.strides)

    @property
    def initial_value(self):
        """(numpy.ndarray) Initial value of the signal.

        Much of the metadata tracked by the Signal is based on this array
        as well (e.g., dtype).
        """
        return self._initial_value

    @initial_value.setter
    def initial_value(self, val):
        raise SignalError("Cannot change initial value after initialization")

    @property
    def is_view(self):
        """(bool) True if this Signal is a view on another Signal."""
        return self._base is not None

    @property
    def itemsize(self):
        """(int) Size of an array element in bytes."""
        return self.initial_value.itemsize

    @property
    def name(self):
        """(str) Name of the signal. Primarily used for debugging."""
        return self._name if self._name is not None else ("0x%x" % id(self))

    @name.setter
    def name(self, name):
        self._name = name

    @property
    def ndim(self):
        """(int) Number of array dimensions."""
        return self.initial_value.ndim

    @property
    def offset(self):
        """(int) Offset of data from base in bytes."""
        return npext.array_offset(self.initial_value)

    @property
    def readonly(self):
        """(bool) Whether associated live data can be changed."""
        return self._readonly

    @readonly.setter
    def readonly(self, readonly):
        self._readonly = bool(readonly)

    @property
    def shape(self):
        """(tuple) Tuple of array dimensions."""
        return self.initial_value.shape

    @property
    def size(self):
        """(int) Total number of elements."""
        return self.initial_value.size

    @property
    def strides(self):
        """(tuple) Strides of data in bytes."""
        return self.initial_value.strides

    def column(self):
        """Return a view on this signal with column vector shape."""
        return self.reshape((self.size, 1))

    def may_share_memory(self, other):
        """Determine if two signals might overlap in memory.

        This comparison is not exact and errs on the side of false positives.
        See `numpy.may_share_memory` for more details.

        Parameters
        ----------
        other : Signal
            The other signal we are investigating.
        """
        return np.may_share_memory(self.initial_value, other.initial_value)

    def reshape(self, *shape):
        """Return a view on this signal with a different shape.

        Note that ``reshape`` cannot change the overall size of the signal.
        See `numpy.reshape` for more details.

        Any number of integers can be passed to this method,
        describing the desired shape of the returned signal.
        """
        return Signal(self._initial_value.reshape(*shape),
                      name="%s.reshape(%s)" % (self.name, shape),
                      base=self.base)

    def row(self):
        """Return a view on this signal with row vector shape."""
        return self.reshape((1, self.size))

    @staticmethod
    def compatible(signals, axis=0):
        for s in signals:
            if s.ndim != signals[0].ndim:
                return False
            if (s.shape[:axis] != signals[0].shape[:axis] or
                    s.shape[axis+1:] != signals[0].shape[axis+1:]):
                return False
            if s.dtype is not signals[0].dtype:
                return False
            if s.is_view:
                if s.base is not signals[0].base:
                    return False
                if s.strides != signals[0].strides:
                    return False
        return True

    @staticmethod
    def check_signals_mergeable(signals, axis=0):
        if any(s.is_view for s in signals):
            raise ValueError("Cannot merge views.")

        for s in signals:
            if s.ndim != signals[0].ndim:
                raise ValueError(
                    "Signals must have the same number of dimensions.")
            if (s.shape[:axis] != signals[0].shape[:axis] or
                    s.shape[axis+1:] != signals[0].shape[axis+1:]):
                raise ValueError(
                    "Signals must have same shape except on concatenation "
                    "axis.")

    @staticmethod
    def merge_signals(signals, replacements, axis=0):
        """Merges multiple signal into one signal with sequential memory
        allocation.

        Note that if any of the signals are linked to another signal (by being
        the base of a view), the merged signal will not reflect
        those links anymore.

        Parameters
        ----------
        signals : sequence
            Signals to merge. Must not contain views.
        axis : int, optional
            Axis along which to concatenate the signals.
        replacements : dict
            Dictionary to update with a mapping from the old signals to new
            signals that are a view into the merged signal and can be used to
            replace the old signals.

        Returns
        -------
        merged_signal : Signal
            The merged signal.
        """
        Signal.check_signals_mergeable(signals, axis=axis)

        initial_value = np.concatenate(
            [s.initial_value for s in signals], axis=axis)
        readonly = all(s.readonly for s in signals)
        name = 'merged<' + str(", ".join(s.name for s in signals)) + '>'
        merged_signal = Signal(initial_value, name=name, readonly=readonly)

        start = 0
        for s in signals:
            size = s.shape[axis]
            indexing = [slice(None)] * initial_value.ndim
            indexing[axis] = slice(start, start + size)
            replacements[s] = merged_signal[tuple(indexing)]
            start += size

        return merged_signal

    @staticmethod
    def check_views_mergeable(signals, axis=0):
        if any(not s.is_view for s in signals):
            raise ValueError("Cannot merge non-views.")

        start = signals[0].offset
        for s in signals:
            if s.base is not signals[0].base:
                raise ValueError("Signals must share the same base.")
            if s.dtype is not signals[0].dtype:
                raise ValueError("Signals must have same dtype.")
            if s.ndim != signals[0].ndim:
                raise ValueError(
                    "Signals must have the same number of dimensions.")
            if s.strides != signals[0].strides:
                raise ValueError("Signals must have equal strides.")
            if (s.shape[:axis] != signals[0].shape[:axis] or
                    s.shape[axis+1:] != signals[0].shape[axis+1:]):
                raise ValueError(
                    "Signals must have same shape except on concatenation "
                    "axis.")
            if s.offset != start:
                raise ValueError("Views are not sequential.")
            start = s.offset + s.size * s.itemsize

    @staticmethod
    def merge_views(signals, axis=0):
        Signal.check_views_mergeable(signals, axis=axis)

        shape = (
            signals[0].shape[:axis] + (sum(s.shape[axis] for s in signals),) +
            signals[0].shape[axis+1:])
        initial_value = np.ndarray(
            buffer=signals[0].base.initial_value, dtype=signals[0].dtype,
            shape=shape, offset=signals[0].offset, strides=signals[0].strides)
        return Signal(
            initial_value, name=signals[0].base.name, base=signals[0].base,
            readonly=all(s.readonly for s in signals))

    @staticmethod
    def merge_signals_or_views(signals, replacements, axis=0):
        are_views = [s.is_view for s in signals]
        if all(are_views):
            return Signal.merge_views(signals, axis=axis)
        elif not any(are_views):
            return Signal.merge_signals(signals, replacements, axis=axis)
        else:
            raise ValueError("Cannot merged mixed views and non-views.")


class SignalDict(dict):
    """Map from Signal -> ndarray

    This dict subclass ensures that the ndarray values aren't overwritten,
    and instead data are written into them, which ensures that
    these arrays never get copied, which wastes time and space.

    Use ``init`` to set the ndarray initially.
    """
    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            if isinstance(key, Signal) and key.base is not key:
                # return a view on the base signal
                base = dict.__getitem__(self, key.base)
                return np.ndarray(
                    buffer=base, dtype=key.dtype, shape=key.shape,
                    offset=key.offset, strides=key.strides)
            else:
                raise

    def __setitem__(self, key, val):
        """Ensures that ndarrays stay in the same place in memory.

        Unlike normal dicts, this means that you cannot add a new key
        to a SignalDict using __setitem__. This is by design, to avoid
        silent typos when debugging Simulator. Every key must instead
        be explicitly initialized with SignalDict.init.
        """
        self[key][...] = val

    def __str__(self):
        """Pretty-print the signals and current values."""
        sio = StringIO()
        for k in self:
            sio.write("%s %s\n" % (repr(k), repr(self[k])))
        return sio.getvalue()

    def init(self, signal):
        """Set up a permanent mapping from signal -> ndarray."""
        if signal in self:
            raise SignalError("Cannot add signal twice")

        x = signal.initial_value
        if signal.is_view:
            if signal.base not in self:
                self.init(signal.base)

            # get a view onto the base data
            offset = npext.array_offset(x)
            view = np.ndarray(shape=x.shape, strides=x.strides, offset=offset,
                              dtype=x.dtype, buffer=self[signal.base].data)
            view.setflags(write=not signal.readonly)
            dict.__setitem__(self, signal, view)
        else:
            x = x.view() if signal.readonly else x.copy()
            dict.__setitem__(self, signal, x)

    def reset(self, signal):
        """Reset ndarray to the base value of the signal that maps to it"""
        if not signal.readonly:
            self[signal] = signal.initial_value
