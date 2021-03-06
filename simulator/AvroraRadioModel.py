
from data.restricted_eval import restricted_eval

class AvroraRadioModel(object):
    def __str__(self):
        return type(self).__name__ + "()"

class LossyRadioModel(AvroraRadioModel):
    def avrora_options(self):
        return {
            "lossy-model": "true"
        }

class RangeRadioModel(AvroraRadioModel):
    def __init__(self, radio_range):
        super().__init__()
        self.radio_range = float(radio_range)

    def avrora_options(self):
        return {
            "radio-range": self.radio_range
        }

    def __str__(self):
        return "{}(radio_range={})".format(type(self).__name__, self.radio_range)


def models():
    """A list of the names of the available medium models."""
    return AvroraRadioModel.__subclasses__()  # pylint: disable=no-member

def eval_input(source):
    result = restricted_eval(source, models())

    if isinstance(result, AvroraRadioModel):
        return result
    else:
        raise RuntimeError(f"The medium model ({source}) is not valid.")

def available_models():
    class WildcardModelChoice(object):
        """A special available model that checks if the string provided
        matches the name of the class."""
        def __init__(self, cls):
            self.cls = cls

        def __eq__(self, value):
            return isinstance(value, self.cls)

        def __repr__(self):
            return self.cls.__name__ + "(...)"

    return [WildcardModelChoice(x) for x in models()]
