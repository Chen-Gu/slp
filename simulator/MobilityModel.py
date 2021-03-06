from collections import OrderedDict
import math
import random

from data.restricted_eval import restricted_eval

class MobilityModel(object):
    def __init__(self):
        self.configuration = None
        self.active_times = None

    def setup(self, configuration):
        raise NotImplementedError()

    def _setup_impl(self, configuration, times):
        self.configuration = configuration
        self.active_times = times

        self._validate_times()

    def _validate_times(self):
        """Checks if the list of time intervals is valid"""

        nodes = self.configuration.topology.nodes

        for (node_id, intervals) in self.active_times.items():
            if node_id not in nodes:
                raise RuntimeError(f"Invalid node id {node_id}.")

            if node_id in self.configuration.sink_ids:
                raise RuntimeError("The source node cannot move onto the sink as it cannot detect it")

    def build_arguments(self):
        build_arguments = {}

        def to_tinyos_format(time):
            if math.isinf(time):
                return "UINT32_MAX"
            else:
                return f"{int(time * 1000)}U"

        indexes = []
        periods = []
        periods_lengths = []

        for (node_idx, (node_id, intervals)) in enumerate(self.active_times.items()):

            # Node IDs must be passed in topology order!
            indexes.append(f"{self.configuration.topology.o2t(node_id)}U")

            period = [
                #"[{node_idx}][{interval_idx}].from = {from_time}, [{node_idx}][{interval_idx}].to = {to_time}".format(
                f"{{{to_tinyos_format(begin)}, {to_tinyos_format(end)}}}"
                for (interval_idx, (begin, end))
                in enumerate(intervals)
            ]

            periods.append("{" + ", ".join(period) + "}")

            periods_lengths.append(f"{len(period)}U")

        build_arguments["SOURCE_DETECTED_INDEXES"] = "{ " + ", ".join(indexes) + " }"
        build_arguments["SOURCE_DETECTED_PERIODS"] = "{ " + ", ".join(periods) + " }"
        build_arguments["SOURCE_DETECTED_PERIODS_LENGTHS"] = "{ " + ", ".join(periods_lengths) + " }"
        build_arguments["SOURCE_DETECTED_NUM_NODES"] = f"{len(indexes)}U"
        build_arguments["SOURCE_DETECTED_NUM_CHANGES"] = max(periods_lengths)

        return build_arguments

    @staticmethod
    def _build_time_list_from_path(node_path, duration, start_time=0):
        current_time = start_time

        times = OrderedDict()

        for (i, node) in enumerate(node_path):
            end_time = current_time + duration if (i + 1) != len(node_path) else float('inf')

            if node not in times:
                times[node] = [(current_time, end_time)]
            else:
                times[node].append((current_time, end_time))

            current_time += duration

        return times


    def __str__(self):
        return type(self).__name__ + "()"

class StationaryMobilityModel(MobilityModel):
    """The default source mobility model, where the source just stays where it is."""

    def __init__(self):
        super().__init__()

    def setup(self, configuration):
        times = OrderedDict()

        for source_id in configuration.source_ids:
            times[source_id] = [(0, float('inf'))]

        self._setup_impl(configuration, times)

class RandomWalkMobilityModel(MobilityModel):
    def __init__(self, max_time, duration, seed):
        super().__init__()

        # There needs to be a finite length to the random walk!
        self.max_time = max_time

        # Duration is the length for which a node will act as a source node.
        self.duration = duration

        self.seed = seed

    def _generate_edge_walk_path(self, configuration, source_id):
        rng = random.Random(self.seed)

        path = [source_id]

        max_length = int(self.max_time / self.duration)

        for i in range(max_length):
            neighbours = list(configuration.one_hop_neighbours(path[-1]))

            path.append(rng.choice(neighbours))

        return path

    def setup(self, configuration):
        times = OrderedDict()

        for source_id in configuration.source_ids:
            path = self._generate_edge_walk_path(configuration, source_id)

            times.update(self._build_time_list_from_path(path, self.duration))

        self._setup_impl(configuration, times)

    def __str__(self):
        return f"{type(self).__name__}(max_time={self.max_time}, duration={self.duration})"


class TowardsSinkMobilityModel(MobilityModel):
    """Generate a path that has the source nodes move towards the sink
    every :duration: time units."""

    def __init__(self, duration):
        super().__init__()
        self.duration = duration

    def setup(self, configuration):
        times = OrderedDict()

        for source_id in configuration.source_ids:
            path = configuration.shortest_path(source_id, configuration.sink_id)

            # Remove the last element from the list as the sink cannot become a source
            path = path[:-1]

            times.update(self._build_time_list_from_path(path, self.duration))

        self._setup_impl(configuration, times)

    def __str__(self):
        return f"{type(self).__name__}(duration={self.duration})"


class RoundNetworkEdgeMobilityModel(MobilityModel):
    def __init__(self, max_time, duration):
        super().__init__()
        
        # There needs to be a finite length to the random walk!
        self.max_time = max_time

        # Duration is the length for which a node will act as a source node.
        self.duration = duration

    def _generate_edge_walk_path(self, configuration, source_id):
        path = [source_id]

        max_length = int(self.max_time / self.duration)

        for i in range(max_length):
            try:
                prev = path[-2]
            except IndexError:
                prev = None

            start = path[-1]

            possible = [x for x in configuration.one_hop_neighbours(start) if x != prev]

            neighbour = min(possible, key=lambda x: len(list(configuration.one_hop_neighbours(x))))

            path.append(neighbour)

        return path

    def setup(self, configuration):
        times = OrderedDict()

        for source_id in configuration.source_ids:
            path = self._generate_edge_walk_path(configuration, source_id)

            times.update(self._build_time_list_from_path(path, self.duration))

        self._setup_impl(configuration, times)

    def __str__(self):
        return f"{type(self).__name__}(max_time={self.max_time},duration={self.duration})"    


def models():
    """A list of the names of the available models."""
    return MobilityModel.__subclasses__() # pylint: disable=no-member

def eval_input(source):
    result = restricted_eval(source, models())

    if result in models():
        raise RuntimeError(f"The source mobility model ({source}) is not valid. (Did you forget the brackets after the name?)")

    if not isinstance(result, MobilityModel):
        raise RuntimeError(f"The source mobility model ({source}) is not valid.")

    return result
