import boto3
import sys
import argparse
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Clean up Application Discovery Service resources.')
    parser.add_argument('-a', '--app-name', 
                        help=f'The application name of the resources to clean up.')
    parser.add_argument('-k', '--tag-key', 
                        help=f'The tag key of the resources to clean up.')
    parser.add_argument('-v', '--tag-value',
                        help='The tag value of the resources to clean up.')
    parser.add_argument('-f', '--force', action='store_true', 
                        help='Force deletion of resources.')
    parser.add_argument('-u', '--unattended', action='store_true', 
                        help='Run the script without asking for confirmation.')
    args = parser.parse_args()
    
    return args

class ADS:
    """Class for interacting with AWS Application Discovery Service."""

    def __init__(self, app_name=None, tag_key=None, tag_value=None, force=None, unattended=None):
        """Initialize with tag key, tag value, and force flag."""
        self.app_name = app_name
        self.tag_key = tag_key
        self.tag_value = tag_value
        self.force = force
        self.unattended = unattended
        self.session = boto3.Session()
        self.discovery_client = self.session.client('discovery')
        logging.info(f"Cleaning up Application Discovery Service resources with application name: {self.app_name}, tag: {self.tag_key}, and value: {self.tag_value}, force flag setting: {self.force}, unattended settings: {self.unattended}")
        
    def list_configurations(self):
        """List configurations matching the tag key and value. Return a list of configurations."""
        logger.info("Listing configurations...")
        try:
            paginator = self.discovery_client.get_paginator('list_configurations')
            configurations = []
            filters = []

            filter_params = [
                (self.app_name, 'server.application.name'),
                (self.tag_key, 'server.tag.key'),
                (self.tag_value, 'server.tag.value')
            ]

            for param, filter_name in filter_params:
                if param is not None:
                    filters.append({
                        'name': filter_name,
                        'values': [param],
                        'condition': 'EQ'
                    })

            for page in paginator.paginate(
                configurationType='SERVER',
                filters=filters
            ):
                configurations.extend(page.get('configurations', []))
            if not configurations:
                logger.warning("No configurations found, exiting...")
                return
            else:
                logger.info(f"Found configurations: {configurations}")
                if not self.unattended:
                    confirmation = input("Do you want to cleanup these configurations? (Type 'cleanup'): ")
                    if confirmation.lower() != 'cleanup':
                        logger.info("Operation cancelled by user.")
                        sys.exit(0)
            return configurations
        except Exception as e:
            raise Exception(f"Error listing configurations: {e}") from e

    def delete_agents(self, agent_ids):
        """Delete agents with the given IDs. Print any errors that occur."""
        logging.info("Deleting agents...")
        try:
            agents_to_delete = [{'agentId': agent_id, 'force': self.force} for agent_id in agent_ids]
            response = self.discovery_client.batch_delete_agents(deleteAgents=agents_to_delete)
            
            # Check for errors in the response
            errors = response.get('errors', [])
            if errors:
                error_messages = []
                for error in errors:
                    error_messages.append(f"Agent {error['agentId']}: {error['errorMessage']}")
                raise Exception('\n'.join(error_messages))
            logging.info(f"Deleted agents: {agent_ids}")
        except Exception as e:
            raise Exception(f"Error deleting agents: {e}")
        
    def delete_configurations(self, configuration_ids):
        logging.info("Deleting configurations...")
        try:
            self.discovery_client.start_batch_delete_configuration_task(
                configurationType='SERVER',
                configurationIds=configuration_ids
            )
            logging.info(f"Deleted configurations: {configuration_ids}")
        except Exception as e:
            raise Exception(f"Error deleting configurations: {e}")

def main():
    """Command line script execution."""
    try:
        args = parse_args()
        
        # Check if any arguments were passed
        if len(sys.argv) == 1:
            print("No flags were provided. Run the tool with -h to learn about more options.")
            sys.exit(1)
        discovery = ADS(args.app_name, args.tag_key, args.tag_value, args.force,args.unattended)
        configurations = discovery.list_configurations()
        if configurations is not None:
            agent_ids = [server['server.agentId'] for server in configurations]
            configuration_ids = [server['server.configurationId'] for server in configurations]
            discovery.delete_agents(agent_ids)
            discovery.delete_configurations(configuration_ids)

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()