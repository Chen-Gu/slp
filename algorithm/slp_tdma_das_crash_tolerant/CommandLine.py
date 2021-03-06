from __future__ import print_function, division

import itertools
import os
import datetime

from simulator import CommandLineCommon
import simulator.sim
import simulator.Configuration

import algorithm

slp_tdma_das = algorithm.import_algorithm("slp_tdma_das")

from data import results, submodule_loader
from data.run.common import RunSimulationsCommon
from data.graph import summary, versus
from data.table import safety_period
from data.util import scalar_extractor

class RunSimulations(RunSimulationsCommon):
    def _get_safety_period(self, darguments):
        # tafn = super(RunSimulations, self)._get_safety_period(darguments)

        #XXX Ugly hack using 0 as seed but we need the config only for SSD
        configuration = simulator.Configuration.create(darguments["configuration"], {"seed":0, **darguments})
        (source_id,) = configuration.source_ids
        (sink_id,) = configuration.sink_ids

        network_size = darguments["network size"]
        # search_distance = darguments["search distance"]
        dissem_period = darguments["dissem period"]
        slot_period = darguments["slot period"]
        tdma_num_slots = darguments["tdma num slots"]
        tdma_period_length = dissem_period + (slot_period * tdma_num_slots)
        ssd = configuration.ssd(sink_id, source_id)
        # change_distance = ssd // 3
        # path_length = search_distance + change_distance

        # return path_length*tdma_period_length
        return (1 + ssd)*tdma_period_length*1.5

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(True, RunSimulations)

        subparser = self._add_argument("graph", self._run_graph)
        subparser = self._add_argument("graph-versus-baseline", self._run_graph_versus_baseline)
        subparser = self._add_argument("graph-min-max", self._run_graph_min_max)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

    def _cluster_time_estimator(self, sim, args, **kwargs):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        size = args['network size']
        if size == 7:
            return datetime.timedelta(hours=8)
        elif size == 11:
            return datetime.timedelta(hours=8)
        elif size == 15:
            return datetime.timedelta(hours=8)
        elif size == 21:
            return datetime.timedelta(hours=8)
        elif size == 25:
            return datetime.timedelta(hours=8)
        else:
            raise RuntimeError("No time estimate for network sizes other than 7, 11, 15, 21 or 25")

    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models,
            parameters.communication_models, parameters.fault_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods, parameters.slot_period, parameters.dissem_period,
            parameters.tdma_num_slots, parameters.slot_assignment_interval, parameters.minimum_setup_periods,
            parameters.pre_beacon_periods, parameters.search_distance,
            [parameters.timesync], parameters.timesync_periods
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

        argument_product = self.add_extra_arguments(argument_product, extras)

        argument_product = self.adjust_source_period_for_multi_source(sim, argument_product)

        return argument_product

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'attacker distance': ('Meters', 'left top'),
            'crash': ('Number of crash messages sent', 'left top'),
        }

        slp_tdma_das_crash_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            network_size_normalisation="UseNumNodes")

        for (vary, vary_prefix) in [("source period", " seconds")]:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-{}'.format(yaxis.replace(" ", "_"), vary.replace(" ", "-"))

                g = versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis='network size', yaxis=yaxis, vary=vary,
                    yextractor=scalar_extractor)

                g.xaxis_label = 'Number of Nodes'
                g.yaxis_label = yaxis_label
                g.vary_label = vary.title()
                g.vary_prefix = vary_prefix
                g.key_position = key_position

                g.create(slp_tdma_das_crash_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name))
                ).run()

    def _run_graph_versus_baseline(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'attacker distance': ('Meters', 'left top'),
            'norm(sent,time taken)': ('Messages Sent per Second', 'left top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
        }

        varying = [
            (('network size', ''), ('source period', ' seconds')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
        }

        self._create_baseline_versus_graph(slp_tdma_das, graph_parameters, varying, custom_yaxis_range_max,
            force_vvalue_label=True,
            result_label="Crash Tolerant SLP TDMA DAS",
            baseline_label="SLP TDMA DAS",
            nokey=True,
            generate_legend_graph=True,
            legend_font_size='8',
        )

    def _run_graph_min_max(self, args):
        graph_parameters = {
            'normal': ('Normal messages sent', 'left top'),
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'attacker distance': ('Meters', 'left top'),
            'norm(sent,time taken)': ('Messages Sent per Second', 'left top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
            'control sent': ('SLP control messages sent', 'left top'),
            'path sent': ('Path creation messages sent', 'left top'),
            'overhead': ('SLP message overhead (%)', 'left top'),
        }

        varying = [
            (('network size', ''), ('source period', ' seconds')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
            'overhead': 2.0,
            'captured': 25,
        }

        font = "',20'"

        self._create_min_max_versus_graph(
            args.sim, [slp_tdma_das], None, graph_parameters, varying,
            custom_yaxis_range_max=custom_yaxis_range_max,
            min_label=['SLP TDMA DAS - Lowest'],
            max_label=['SLP TDMA DAS - Highest'],
            vary_label="",
            comparison_label='Crash Tolerant SLP TDMA DAS',

            force_vvalue_label=True,
            #result_label="Crash Tolerant SLP TDMA DAS",
            #baseline_label="SLP TDMA DAS",
            nokey=True,
            generate_legend_graph=True,
            legend_font_size='20',
            network_size_normalisation="UseNumNodes",
            xaxis_font=font, yaxis_font=font,
            xlabel_font=font, ylabel_font=font
        )
