from __future__ import print_function

import os

import data.util
from data import latex
from data.graph.versus import Grapher as GrapherBase

class Grapher(GrapherBase):
    def __init__(self, output_directory,
            result_name, xaxis, yaxis, vary, yextractor=lambda x: x):

        super(Grapher, self).__init__(output_directory, result_name, xaxis, yaxis, vary, yextractor)

        self.max_label = 'Maximum'
        self.min_label = 'Minimum'
        self.comparison_label = 'Comparison'

    def create(self, comparison_results, actual_results):
        print('Removing existing directories')
        data.util.remove_dirtree(os.path.join(self.output_directory, self.result_name))

        print('Creating {} graph files'.format(self.result_name))

        dat = {}

        min_comparison_results = {}
        max_comparison_results = {}

        # Find the min and max results over all parameter combinations 
        for ((size, config), items1) in comparison_results.data.items():
            for (src_period, items2) in items1.items():

                local_min = None
                local_max = None

                for (params, results) in items2.items():
                    yvalue = results[ comparison_results.result_names.index(self.yaxis) ]
                    yvalue = self.yextractor(yvalue)

                    local_min = yvalue if local_min is None else min(local_min, yvalue)
                    local_max = yvalue if local_max is None else max(local_max, yvalue)

                min_comparison_results.setdefault((size, config), {})[src_period] = local_min
                max_comparison_results.setdefault((size, config), {})[src_period] = local_max


        # Extract the data we want to display
        for ((size, config), items1) in actual_results.data.items():
            for (src_period, items2) in items1.items():
                for (params, results) in items2.items():

                    key_names = ['size', 'configuration', 'source period'] + actual_results.parameter_names

                    values = [size, config, src_period] + list(params)

                    (key_names, values, xvalue) = self.remove_index(key_names, values, self.xaxis)
                    (key_names, values, vvalue) = self.remove_index(key_names, values, self.vary)

                    key_names = tuple(key_names)
                    values = tuple(values)

                    yvalue = results[ actual_results.result_names.index(self.yaxis) ]
                    yvalue = self.yextractor(yvalue)

                    comp_label = "{} ({})".format(self.comparison_label, latex.escape(vvalue))

                    dat.setdefault((key_names, values), {})[(xvalue, self.max_label)] = max_comparison_results[(size, config)].get(src_period)
                    dat.setdefault((key_names, values), {})[(xvalue, comp_label)] = yvalue
                    dat.setdefault((key_names, values), {})[(xvalue, self.min_label)] = min_comparison_results[(size, config)].get(src_period)


        for ((key_names, key_values), values) in dat.items():
            self._create_plot(key_names, key_values, values)

        self._create_graphs(self.result_name)