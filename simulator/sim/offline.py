import sys
import os.path
import importlib

def parsers():
    return [
        ("SINGLE", None, ["verbose", "configuration", "attacker model", "fault model", "safety period",
                          "seed", "log file", "log converter", "nonstrict", "extra metrics", "show raw log"]),
        ("GUI", "SINGLE", ["gui scale"]),
    ]

def build(module, a):
    pass

def print_version():
    pass

def print_arguments(module_name, a):
    # Try to extract parameters from the log file name

    names = {os.path.dirname(name).rsplit("_", 1)[0] for name in a.args.log_file}

    if len(names) != 1:
        raise RuntimeError("Multiple names")
        
    name = os.path.basename(next(iter(names)))

    params = name.split("-")

    module = importlib.import_module(module_name)
    local_parameter_names = module.local_parameter_names

    # Some testbeds need short names, so the default fault model may be omitted
    if len(params) == 5 + len(local_parameter_names):
        (configuration, rf_power, channel, lpl, source_period) = params[:5]
        del params[:5]
        
        fault_model = "ReliableFaultModel()"

    #elif len(params) == 3 + len(local_parameter_names):
    #    (configuration, source_period) = params[:2]
    #    del params[:2]

    #    fault_model = "ReliableFaultModel()"

    else:
        raise RuntimeError("Don't know how to work out what these parameters are")

    if configuration != a.args.configuration:
        raise RuntimeError(f"Configuration ({configuration}) differs from the one specified ({a.args.configuration})")

    if fault_model != str(a.args.fault_model):
        raise RuntimeError(f"FaultModel ({fault_model}) differs from the one specified ({a.args.fault_model})")

    # Last Parameter is always rf power
    #rf_power = params.pop(-1)

    local_parameter_values = zip(local_parameter_names, params)

    source_period = float(source_period.replace("_", "."))
    print(f"source_period=FixedPeriodModel(period={source_period})")

    for (name, value) in local_parameter_values:
        print(f"{name}={value}".replace(" ", "_"))

    print(f"rf_power={rf_power}")
    print(f"channel={channel}")
    print(f"low_power_listening={lpl}")

    for (k, v) in sorted(vars(a.args).items()):
        if k not in a.arguments_to_hide:
            print(f"{k}={v}")

def run_one_file(log_file, module, a, count=1, print_warnings=False):
    import simulator.Configuration as Configuration
    import simulator.OfflineLogConverter as OfflineLogConverter

    # Get the correct Simulation constructor
    if a.args.mode == "SINGLE":
        from simulator.Simulation import OfflineSimulation
    elif a.args.mode == "GUI":
        from simulator.TosVis import GuiOfflineSimulation as OfflineSimulation
    else:
        raise RuntimeError(f"Unknown mode {a.args.mode}")

    configuration = Configuration.create(a.args.configuration, a.args)

    if a.args.verbose:
        print(f"Analysing log file {log_file}", file=sys.stderr)

    with OfflineLogConverter.create_specific(a.args.log_converter, log_file) as converted_event_log:
        with OfflineSimulation(module, configuration, a.args, event_log=converted_event_log) as sim:

            a.args.attacker_model.setup(sim)

            try:
                sim.run()
            except Exception as ex:
                import traceback

                all_args = "\n".join(f"{k}={v}" for (k, v) in vars(a.args).items())

                print("Killing run due to {}".format(ex), file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                print("For parameters:", file=sys.stderr)
                print("With seed:", sim.seed, file=sys.stderr)
                print(all_args, file=sys.stderr)
                print("In file: {}".format(log_file), file=sys.stderr)

                return 51

            try:
                sim.metrics.print_results()

                if print_warnings:
                    sim.metrics.print_warnings()

            except Exception as ex:
                import traceback

                all_args = "\n".join(f"{k}={v}" for (k, v) in vars(a.args).items())

                print("Failed to print metrics due to: {}".format(ex), file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                print("For parameters:", file=sys.stderr)
                print("With seed:", sim.seed, file=sys.stderr)
                print(all_args, file=sys.stderr)
                print("In file: {}".format(log_file), file=sys.stderr)
                
                return 52

    return 0

def run_simulation(module, a, count=1, print_warnings=False):
    overall_return = 0

    for log_file in a.args.log_file:
        ret = run_one_file(log_file, module, a, count=count, print_warnings=print_warnings)

        if ret != 0:
            overall_return = ret

    return overall_return
