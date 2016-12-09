from __future__ import print_function, division

import itertools
import os

from simulator import CommandLineCommon

import algorithm

protectionless_tdma_das = algorithm.import_algorithm("protectionless_tdma_das")

from data import results
from data.run.common import RunSimulationsCommon
from data.graph import summary, versus
from data.table import safety_period
from data.util import scalar_extractor

class RunSimulations(RunSimulationsCommon):
    def _get_safety_period(self, darguments):
        time_taken = super(RunSimulations, self)._get_safety_period(darguments)

        # minimum_setup_period = darguments["minimum setup periods"]
        # tdma_safety_period = darguments["tdma safety periods"]
        # dissem_period = darguments["dissem period"]
        # slot_period = darguments["slot period"]
        # tdma_num_slots = darguments["tdma num slots"]

        # period_length_sec = dissem_period + (slot_period * tdma_num_slots)
        # tdma_safety_period = int(time_taken / period_length_sec) - minimum_setup_periods + 1

        # return (minimum_setup_period + tdma_safety_period) * period_length_sec
        return time_taken

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless_tdma_das.result_file_path, RunSimulations)

        subparser = self._subparsers.add_parser("graph")

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods, parameters.slot_period, parameters.dissem_period,
            parameters.tdma_num_slots, parameters.slot_assignment_interval, parameters.minimum_setup_periods,
            parameters.pre_beacon_periods, parameters.dissem_timeout, parameters.search_distance
        ))

        # argument_product = list(itertools.product(
            # parameters.sizes, parameters.configurations,
            # parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            # [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            # parameters.source_periods, parameters.slot_periods, parameters.dissem_periods,
            # parameters.tdma_num_slots, parameters.slot_assignment_intervals, parameters.minimum_setup_periods,
            # parameters.pre_beacon_periods, parameters.dissem_timeouts, parameters.tdma_safety_periods_and_search_distances
        # ))

        # argument_product = [
                # (s, c, am, nm, cm, d, nido, lnst, src_period, sp, dp, ts, ai, msp, pbp, dt, sd, tsp)
            # for (s, c, am, nm, cm, d, nido, lnst, src_period, sp, dp, ts, ai, msp, pbp, dt, (tsp, sd))
            # in  argument_product
        # ]

        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'attacker distance': ('Meters', 'left top'),
        }

        slp_tdma_das_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()))

        for (vary, vary_prefix) in [("source period", " seconds")]:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-{}'.format(yaxis.replace(" ", "_"), vary.replace(" ", "-"))

                g = versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis='network size', yaxis=yaxis, vary=vary,
                    yextractor=scalar_extractor)

                g.xaxis_label = 'Network Size'
                g.yaxis_label = yaxis_label
                g.vary_label = vary.title()
                g.vary_prefix = vary_prefix
                g.key_position = key_position

                g.create(slp_tdma_das_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name))
                ).run()

    def _run_min_max_versus(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'normal': ('Normal Messages Sent', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'attacker distance': ('Attacker Distance From Source (meters)', 'left top'),
        }

        custom_yaxis_range_max = {
        }

        protectionless_tdma_das_results = results.Results(
            protectionless_tdma_das.result_file_path,
            parameters=protectionless_tdma_das.local_parameter_names,
            results=list(set(graph_parameters.keys()) & set(protectionless_tdma_das_results.Analysis.Analyzer.results_header().keys())))

        slp_tdma_das_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=graph_parameters.keys())

    def run(self, args):
        args = super(CLI, self).run(args)

        if 'graph' == args.mode:
            self._run_graph(args)
