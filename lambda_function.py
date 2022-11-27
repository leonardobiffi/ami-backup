#! /usr/bin/python

import datetime
import json
from urllib import request
import json
import boto3
import os
from dateutil.tz import UTC

CUSTOMER = os.environ["CUSTOMER"]
REGION = os.environ["REGION"]
RETENTION_DAYS = int(os.environ["RETENTION_DAYS"])
SLACK_ENABLED = os.environ["SLACK_ENABLED"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]


def slack(message):
    """
    This function is used to post message to slack.
    """
    post = {"text": "{0}".format(message)}

    try:
        json_data = json.dumps(post)
        req = request.Request(SLACK_WEBHOOK_URL, data=json_data.encode(
            'ascii'), headers={'Content-Type': 'application/json'})
        resp = request.urlopen(req)
    except Exception as em:
        print("EXCEPTION: " + str(em))


def delete_ami(image_jsonresponse, days_older, ec2, region):
    """
    This function deletes AMI older than number of days to keep AMI.
    ex. The tag Key:RetentionDays, Value:7 will retein AMI for 7 days, ignoring default in lambda_handler
    """
    for i in image_jsonresponse['Images']:

        # get RetentionDays in TAG
        try:
            retention_days = [int(t.get('Value')) for t in i['Tags'] if t['Key'] == 'RetentionDays'][0]
        except IndexError:
            retention_days = days_older
        except ValueError:
            retention_days = days_older
        except Exception as e:
            retention_days = days_older

        right_now_days_ago = datetime.datetime.today() - datetime.timedelta(days=retention_days - 1)
        old_date = right_now_days_ago.replace(tzinfo=UTC)

        if i['CreationDate'] < str(old_date):
            image_id = i['ImageId']
            print('Image ID' + str(image_id))
            delimage = ec2.Image(image_id)
            snap_list = []

            for j in i['BlockDeviceMappings']:
                if 'Ebs' in j:
                    snap_list.append(j['Ebs']['SnapshotId'])

            try:
                response = delimage.deregister()
                for k in range(len(snap_list)):
                    snapshot = ec2.Snapshot(snap_list[k])
                    reponse = snapshot.delete()
                    print("AMI snapshot ID deleted " + snap_list[k])
            except Exception as e:
                print(e)
                message = 'Cliente: ' + CUSTOMER + '\nError while deleting image\nImageId:'+image_id+' \
                        \nRegion:'+region+'\nException:'+str(e)
                
                if SLACK_ENABLED == "true":
                    slack(message)
                else:
                    print(message)


def create_ami(instance_jsonresponse, ec2, region):
    """
    This function creates new AMI with tags for the instance which got backup tag.
    """
    for i in instance_jsonresponse['Reservations']:
        for j in i['Instances']:
            print('Instance ID: ' + str(j['InstanceId']))
            iid = j['InstanceId']
            tag_key_list = []
            tag_value_list = []
            instance = ec2.Instance(iid)

            for k in instance.tags:
                # Not use tag aws: because is reserved
                if 'aws:' not in k['Key']:
                    tag_key_list.append(k['Key'])
                    tag_value_list.append(k['Value'])
                if k['Key'] == 'Name':
                    dscrip = k['Value']

            try:
                image = instance.create_image(
                    Name=dscrip + "-" +
                    str(datetime.datetime.now().strftime('%Y-%m-%d_%H_%M_%S.%f')),
                    NoReboot=True
                )

                for l in range(len(tag_key_list)):
                    tag = image.create_tags(
                        Tags=[
                            {
                                'Key': tag_key_list[l],
                                'Value': tag_value_list[l]
                            }
                        ]
                    )

                tag = image.create_tags(
                    Tags=[
                        {
                            # Tag required to fetch all the AMI's to delete.
                            'Key': 'DELETE_ON',
                            'Value': 'yes'
                        },
                        {
                            # Tag required to fetch all the snapshots associated to AMI in order to tag those snapshots.
                            'Key': 'SNAPSHOT_TAG',
                            'Value': 'yes'
                        }
                    ]
                )
            except Exception as e:
                print(e)
                message = 'Cliente: ' + CUSTOMER + '\nError while creating image of instance\n\nInstanceId:' + iid + ' \
                        \nRegion:' + region + '\n\n Exception:' + str(e)
                
                if SLACK_ENABLED == "true":
                    slack(message)
                else:
                    print(message)


def tag_snapshots(new_image_jsonresponse, client, region):
    """
    This function tags all the snapshots which are associated to new AMI's created.
    """
    for i in new_image_jsonresponse['Images']:
        image_id = i['ImageId']
        print('ImageID: ' + str(image_id))
        snap_tag_key_list = []
        snap_tag_value_list = []

        for k in i['Tags']:
            # Not use tag aws: because is reserved
            if 'aws:' not in k['Key']:
                snap_tag_key_list.append(k['Key'])
                snap_tag_value_list.append(k['Value'])

        for j in i['BlockDeviceMappings']:
            if 'Ebs' in j and 'SnapshotId' in j['Ebs']:
                snapid = j["Ebs"]["SnapshotId"]

            try:
                for l in range(len(snap_tag_key_list)):
                    responsetag = client.create_tags(
                        Resources=[
                            snapid,
                        ],
                        Tags=[
                            {
                                'Key': snap_tag_key_list[l],
                                'Value': snap_tag_value_list[l],
                            }
                        ],
                    )
            except Exception as e:
                print(e)
                message = 'Cliente: ' + CUSTOMER + '\nError while creating tags on snapshots of AMI\nAMIId:'+image_id+' \
                        \nRegion:'+region+'\nException:' + str(e)
                
                if SLACK_ENABLED == "true":
                    slack(message)
                else:
                    print(message)

        delete_tag = client.delete_tags(
            Resources=[
                image_id,
            ],
            Tags=[
                {
                    'Key': 'SNAPSHOT_TAG',
                    'Value': 'yes'
                },
            ]
        )


def amibkp(region, days_del):
    """
    This function is the crucial function,
    fetches all the instances which has tag Key:Backup, Value:true and creates AMI in a loop,
    along with propogating all the tags from instance to AMI to EBS Snapshots.
    Also, it deletes all the AMI's which was created through this script
    and older than number of days you provide as an argument.
    Parameters
    ----------
    region: string
          AWS region code.
    days: integer
          Number of days to keep AMI's before deleting.
    Returns
    -------
    list
        Returns list of AMI's/Snapshots deleted and newly created AMI's/Snapshots.
    """
    client = boto3.client('ec2', region_name=region)
    ec2 = boto3.resource('ec2', region_name=region)

    image_response = client.describe_images(
        Filters=[
            {
                'Name': 'tag:DELETE_ON',
                'Values': ['yes']
            },
        ]
    )

    delete_ami(image_response, days_del, ec2, region)

    instance_response = client.describe_instances(
        Filters=[
            {
                # Tag trued to identify list of Instances to be backed up.
                'Name': 'tag:Backup',
                'Values': ['true', 'True']
            }
        ]
    )

    create_ami(instance_response, ec2, region)

    new_image_response = client.describe_images(
        Filters=[
            {
                'Name': 'tag:SNAPSHOT_TAG',
                'Values': ['yes']
            },
        ]
    )

    tag_snapshots(new_image_response, client, region)


def lambda_handler(event, context):
    amibkp(REGION, RETENTION_DAYS)
