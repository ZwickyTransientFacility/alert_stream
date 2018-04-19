#!/usr/bin/env python

"""Consumes stream for printing all messages to the console.

Note that consumers with the same group ID share a stream.
To run multiple consumers each printing all messages,
each consumer needs a different group.
"""

from __future__ import print_function
import argparse
import sys
import os
from lsst.alert.stream import alertConsumer


def msg_text(message):
    """Remove postage stamp cutouts from an alert message.
    """
    message_text = {k: message[k] for k in message
                    if k not in ['cutoutDifference', 'cutoutTemplate', 'cutoutScience']}
    return message_text


def write_stamp_file(stamp_dict, output_dir):
    """Given a stamp dict that follows the cutout schema,
       write data to a file in a given directory.
    """
    try:
        filename = stamp_dict['fileName']
        try:
            os.makedirs(output_dir)
        except OSError:
            pass
        out_path = os.path.join(output_dir, filename)
        with open(out_path, 'wb') as f:
            f.write(stamp_dict['stampData'])
    except TypeError:
        sys.stderr.write('%% Cannot get stamp\n')
    return


def alert_filter(alert, stampdir=None):
    """Filter to apply to each alert.
       See schemas: https://github.com/ZwickyTransientFacility/ztf-avro-alert
    """
    data = msg_text(alert)
    if data:  # Write your condition statement here
        print(data)  # Print all main alert data to screen
        if stampdir:  # Collect all postage stamps
            write_stamp_file(
                alert.get('cutoutDifference'), stampdir)
            write_stamp_file(
                alert.get('cutoutTemplate'), stampdir)
            write_stamp_file(
                alert.get('cutoutScience'), stampdir)
    return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('topic', type=str,
                        help='Name of Kafka topic to listen to.')
    parser.add_argument('--group', type=str,
                        help='Globally unique name of the consumer group. '
                        'Consumers in the same group will share messages '
                        '(i.e., only one consumer will receive a message, '
                        'as in a queue). Default is value of $HOSTNAME.')
    parser.add_argument('--stampDir', type=str,
                        help='Output directory for writing postage stamp'
                        'cutout files.')
    avrogroup = parser.add_mutually_exclusive_group()
    avrogroup.add_argument('--decode', dest='avroFlag', action='store_true',
                           help='Decode from Avro format. (default)')
    avrogroup.add_argument('--decode-off', dest='avroFlag',
                           action='store_false',
                           help='Do not decode from Avro format.')
    parser.set_defaults(avroFlag=True)

    args = parser.parse_args()

    # Configure consumer connection to Kafka broker
    conf = {'bootstrap.servers': 'epyc.astro.washington.edu:9092,epyc.astro.washington.edu:9093,epyc.astro.washington.edu:9094',
            'default.topic.config': {'auto.offset.reset': 'smallest'}}
    if args.group:
        conf['group.id'] = args.group
    else:
        conf['group.id'] = os.environ['HOSTNAME']

    # Configure Avro reader schema
    schema_files = ["../ztf-avro-alert/schema/candidate.avsc",
                    "../ztf-avro-alert/schema/cutout.avsc",
                    "../ztf-avro-alert/schema/prv_candidate.avsc",
                    "../ztf-avro-alert/schema/alert.avsc"]

    # Start consumer and print alert stream
    streamReader = alertConsumer.AlertConsumer(
                        args.topic, schema_files, **conf)

    while True:
        try:
            msg = streamReader.poll(decode=args.avroFlag)

            if msg is None:
                continue
            else:
                for record in msg:
                    # Apply filter to each alert
                    alert_filter(record, args.stampDir)

        except alertConsumer.EopError as e:
            # Write when reaching end of partition
            sys.stderr.write(e.message)
        except IndexError:
            sys.stderr.write('%% Data cannot be decoded\n')
        except UnicodeDecodeError:
            sys.stderr.write('%% Unexpected data format received\n')
        except KeyboardInterrupt:
            sys.stderr.write('%% Aborted by user\n')
            sys.exit()


if __name__ == "__main__":
    main()
