import Analysis, Arguments, CommandLine, Runner, Metrics

def _setup():
	import algorithm
	return algorithm._setup_algorithm_paths("phantom_reliable")

(name, results_path, result_file, result_file_path, graphs_path) = _setup()