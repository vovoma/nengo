import numpy as np

from nengo.builder import Builder, Operator, Signal
from nengo.neurons import (
    AdaptiveLIF, AdaptiveLIFRate, Izhikevich, LIF, NeuronType)


class SimNeurons(Operator):
    """Set a neuron model output for the given input current.

    Implements ``neurons.step_math(dt, J, output, *states)``.

    Parameters
    ----------
    neurons : NeuronType
        The `.NeuronType`, which defines a ``step_math`` function.
    J : Signal
        The input current.
    output : Signal
        The neuron output signal that will be set.
    states : list, optional (Default: None)
        A list of additional neuron state signals set by ``step_math``.
    tag : str, optional (Default: None)
        A label associated with the operator, for debugging purposes.

    Attributes
    ----------
    J : Signal
        The input current.
    neurons : NeuronType
        The `.NeuronType`, which defines a ``step_math`` function.
    output : Signal
        The neuron output signal that will be set.
    states : list
        A list of additional neuron state signals set by ``step_math``.
    tag : str or None
        A label associated with the operator, for debugging purposes.

    Notes
    -----
    1. sets ``[output] + states``
    2. incs ``[]``
    3. reads ``[J]``
    4. updates ``[]``
    """

    def __init__(self, neurons, J, output, states=None, tag=None):
        super(SimNeurons, self).__init__(tag=tag)
        self.neurons = neurons
        self.J = J
        self.output = output
        self.states = [] if states is None else states

        self.sets = [output] + self.states
        self.incs = []
        self.reads = [J]
        self.updates = []

    def _descstr(self):
        return '%s, %s, %s' % (self.neurons, self.J, self.output)

    def make_step(self, signals, dt, rng):
        J = signals[self.J]
        output = signals[self.output]
        states = [signals[state] for state in self.states]

        def step_simneurons():
            self.neurons.step_math(dt, J, output, *states)
        return step_simneurons

    def can_merge(self, other):
        return (self.__class__ is other.__class__ and
                self.neurons == other.neurons)

    def _gather(self, others, key):
        return [getattr(self, key)] + [getattr(o, key) for o in others]

    def merge(self, others):
        replacements = {}
        J = Signal.merge_signals(self._gather(others, 'J'), replacements)
        output = Signal.merge_signals(
            self._gather(others, 'output'), replacements)
        states = []
        for signals in zip(*self._gather(others, 'states')):
            states.append(Signal.merge_signals(signals, replacements))
        return (SimNeurons(self.neurons, J, output, states), replacements)


@Builder.register(NeuronType)
def build_neurons(model, neurontype, neurons):
    """Builds a `.NeuronType` object into a model.

    This build function works with any `.NeuronType` that does not require
    extra state, like `.RectifiedLinear` and `.LIFRate`. This function adds a
    `.SimNeurons` operator connecting the input current to the
    neural output signals.

    Parameters
    ----------
    model : Model
        The model to build into.
    neurontype : NeuronType
        Neuron type to build.
    neuron : Neurons
        The neuron population object corresponding to the neuron type.

    Notes
    -----
    Does not modify ``model.params[]`` and can therefore be called
    more than once with the same `.NeuronType` instance.
    """

    model.add_op(SimNeurons(neurons=neurontype,
                            J=model.sig[neurons]['in'],
                            output=model.sig[neurons]['out']))


@Builder.register(LIF)
def build_lif(model, lif, neurons):
    """Builds a `.LIF` object into a model.

    In addition to adding a `.SimNeurons` operator, this build function sets up
    signals to track the voltage and refractory times for each neuron.

    Parameters
    ----------
    model : Model
        The model to build into.
    lif : LIF
        Neuron type to build.
    neuron : Neurons
        The neuron population object corresponding to the neuron type.

    Notes
    -----
    Does not modify ``model.params[]`` and can therefore be called
    more than once with the same `.LIF` instance.
    """

    model.sig[neurons]['voltage'] = Signal(
        np.zeros(neurons.size_in), name="%s.voltage" % neurons)
    model.sig[neurons]['refractory_time'] = Signal(
        np.zeros(neurons.size_in), name="%s.refractory_time" % neurons)
    model.add_op(SimNeurons(
        neurons=lif,
        J=model.sig[neurons]['in'],
        output=model.sig[neurons]['out'],
        states=[model.sig[neurons]['voltage'],
                model.sig[neurons]['refractory_time']]))


@Builder.register(AdaptiveLIFRate)
def build_alifrate(model, alifrate, neurons):
    """Builds an `.AdaptiveLIFRate` object into a model.

    In addition to adding a `.SimNeurons` operator, this build function sets up
    signals to track the adaptation term for each neuron.

    Parameters
    ----------
    model : Model
        The model to build into.
    alifrate : AdaptiveLIFRate
        Neuron type to build.
    neuron : Neurons
        The neuron population object corresponding to the neuron type.

    Notes
    -----
    Does not modify ``model.params[]`` and can therefore be called
    more than once with the same `.AdaptiveLIFRate` instance.
    """

    model.sig[neurons]['adaptation'] = Signal(
        np.zeros(neurons.size_in), name="%s.adaptation" % neurons)
    model.add_op(SimNeurons(neurons=alifrate,
                            J=model.sig[neurons]['in'],
                            output=model.sig[neurons]['out'],
                            states=[model.sig[neurons]['adaptation']]))


@Builder.register(AdaptiveLIF)
def build_alif(model, alif, neurons):
    """Builds an `.AdaptiveLIF` object into a model.

    In addition to adding a `.SimNeurons` operator, this build function sets up
    signals to track the voltage, refractory time, and adaptation term
    for each neuron.

    Parameters
    ----------
    model : Model
        The model to build into.
    alif : AdaptiveLIF
        Neuron type to build.
    neuron : Neurons
        The neuron population object corresponding to the neuron type.

    Notes
    -----
    Does not modify ``model.params[]`` and can therefore be called
    more than once with the same `.AdaptiveLIF` instance.
    """

    model.sig[neurons]['voltage'] = Signal(
        np.zeros(neurons.size_in), name="%s.voltage" % neurons)
    model.sig[neurons]['refractory_time'] = Signal(
        np.zeros(neurons.size_in), name="%s.refractory_time" % neurons)
    model.sig[neurons]['adaptation'] = Signal(
        np.zeros(neurons.size_in), name="%s.adaptation" % neurons)
    model.add_op(SimNeurons(neurons=alif,
                            J=model.sig[neurons]['in'],
                            output=model.sig[neurons]['out'],
                            states=[model.sig[neurons]['voltage'],
                                    model.sig[neurons]['refractory_time'],
                                    model.sig[neurons]['adaptation']]))


@Builder.register(Izhikevich)
def build_izhikevich(model, izhikevich, neurons):
    """Builds an `.Izhikevich` object into a model.

    In addition to adding a `.SimNeurons` operator, this build function sets up
    signals to track the voltage and recovery terms for each neuron.

    Parameters
    ----------
    model : Model
        The model to build into.
    izhikevich : Izhikevich
        Neuron type to build.
    neuron : Neurons
        The neuron population object corresponding to the neuron type.

    Notes
    -----
    Does not modify ``model.params[]`` and can therefore be called
    more than once with the same `.Izhikevich` instance.
    """

    model.sig[neurons]['voltage'] = Signal(
        np.ones(neurons.size_in) * izhikevich.reset_voltage,
        name="%s.voltage" % neurons)
    model.sig[neurons]['recovery'] = Signal(
        np.ones(neurons.size_in)
        * izhikevich.reset_voltage
        * izhikevich.coupling, name="%s.recovery" % neurons)
    model.add_op(SimNeurons(neurons=izhikevich,
                            J=model.sig[neurons]['in'],
                            output=model.sig[neurons]['out'],
                            states=[model.sig[neurons]['voltage'],
                                    model.sig[neurons]['recovery']]))
