import logging

from .data_sink_source import muscled_source

if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    muscled_source()
