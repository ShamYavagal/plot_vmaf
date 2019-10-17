#!/usr/bin/env python3
import boto3
import os

from boto3 import resource
from boto3.dynamodb.conditions import Key, Attr
dynamodb = resource('dynamodb', region_name='us-east-1')

table = dynamodb.Table('apiUsers')

def put_user(uid, username, pwd):
    return table.put_item(Item={'user_id': uid, 'username': username, 'password': pwd})

#Controlled By Admin 
put_user('4', os.environ.get('USER1'), os.environ.get('PWD1'))

def get_user_pwd(username, password=None):
    response = table.scan(
    FilterExpression=Key('username').eq(username) & Key('password').eq(password)
)   
    if response.get('Items'):
        return response.get('Items')[0].get('username', None), response.get('Items')[0].get('password', None)
    return None
    

def authenticate(username, password):
    if get_user_pwd(username, password) == (username, password):
        return username, password
    return None


def get_uid(username):
    response = table.scan(
    FilterExpression=Key('username').eq(username)
)   
    if response.get('Items'):
        return response.get('Items')[0].get('Id', None)
    return None

def get_user(username):
    response = table.scan(
    FilterExpression=Key('username').eq(username)
)   
    if response.get('Items'):
        return response.get('Items')[0].get('username', None)
    return None

