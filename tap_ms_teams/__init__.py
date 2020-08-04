import json
import sys

import singer
from singer import Transformer, metadata
from tap_ms_teams.catalog import generate_catalog
from tap_ms_teams.client import MicrosoftGraphClient
from tap_ms_teams.streams import AVAILABLE_STREAMS

LOGGER = singer.get_logger()

def discover(client):
    LOGGER.info('Starting Discovery..')
    streams = [stream_class(client) for _, stream_class in AVAILABLE_STREAMS.items()]
    catalog = generate_catalog(streams)
    json.dump(catalog, sys.stdout, indent=2)

def sync(client, config, catalog, state):
    LOGGER.info('Starting Sync..')
    selected_streams = catalog.get_selected_streams(state)

    streams = []
    stream_keys = []
    with Transformer() as transformer:
        for catalog_entry in selected_streams:
            streams.append(catalog_entry)
            stream_keys.append(catalog_entry.stream)

        for catalog_entry in streams:
            stream = AVAILABLE_STREAMS[catalog_entry.stream](client=client, config=config,
                                                                    catalog=catalog,
                                                                    state=state)
            LOGGER.info('Syncing stream: %s', catalog_entry.stream)
            stream.write_schema()
            replication_key = stream.replication_key
            stream_schema = catalog_entry.schema.to_dict()
            stream_metadata = metadata.to_map(catalog_entry.metadata)
            for page in stream.sync(catalog_entry.metadata):
                for record in page:
                    singer.write_record(
                        catalog_entry.stream,
                        transformer.transform(
                            record, stream_schema, stream_metadata,
                        ))
            stream.write_state()

        LOGGER.info('Finished Sync..')


def main():
    parsed_args = singer.utils.parse_args(required_config_keys=['client_id', 'client_secret', 'tenant_id'])
    config = parsed_args.config

    try:
        client = MicrosoftGraphClient(config)
        client.login()

        if parsed_args.discover:
            discover(client=client)
        elif parsed_args.catalog:
            sync(client, config, parsed_args.catalog, parsed_args.state)
    finally:
        if client:
            if client.login_timer:
                client.login_timer.cancel()


if __name__ == '__main__':
    main()