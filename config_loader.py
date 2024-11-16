import yaml


def load_config(file_name):
    # Load configuration file
    with open(file_name, "r") as config_file:
        config = yaml.safe_load(config_file)

    return config
