import re
from pymongo import MongoClient
import pymongo
from requests import api
from napoleon_connection import config
from datetime import datetime, timedelta
import requests
import json
import urllib.parse

def refresh_dataset(username, request_name):
    payload = json.dumps({ "name": request_name, "user": username})
    headers = {
        'x-api-key': config.valet['x-api-key'],
        'Content-Type': 'application/json'
        }

    response = requests.request("POST", config.valet['url'], headers=headers, data=payload)

    return response

def create_request(formdata, username):
    # create new entry (if exists, report back error)

    client = MongoClient(config.mongodb['uri'])
    db = client[config.mongodb['database']]
    api_requests = db[config.mongodb['request_collection']]

    request = api_requests.find_one({"name": formdata['requestname'], "user": username})

    if request:
        return False, 'Request "{}" exists already.'.format(formdata['requestname'])

    api_requests.insert_one({
        'name': formdata['requestname'],
        'query': '#' + formdata['hashtag'] + ' -is:retweet',
        'parameters': 'max_results=100&tweet.fields=context_annotations,entities,public_metrics,created_at,geo,lang&expansions=author_id,in_reply_to_user_id,geo.place_id,attachments.media_keys&media.fields=duration_ms,preview_image_url,public_metrics,url&user.fields=created_at,location,profile_image_url,public_metrics,verified,description',
        'maintenance_delta': 36,
        'hashtag': formdata['hashtag'],
        'since_id': '',
        'user': username,
        'FirstRunCompleted': False
    })

    return True, 'Request "{}" successfully created.'.format(formdata['requestname'])

def delete_request(request_name, username):
    client = MongoClient(config.mongodb['uri'])
    db = client[config.mongodb['database']]
    api_requests = db[config.mongodb['request_collection']]

    request = api_requests.find_one({"name": request_name, "user": username})

    if not request:
        return False, 'Request "{}" does not exists.'.format(request_name)

    tweets = db[config.mongodb['tweets_collection']]
    tweets.delete_many({"requests": request_name})

    media = db[config.mongodb['media_collection']]
    media.delete_many({"requests": request_name})

    api_requests.delete_one({"name": request_name, "user": username})

    return True, 'Data of request "{}" successfully deleted.'.format(request_name)


def get_dashboards(username):
    client = MongoClient(config.mongodb['uri'])
    db = client[config.mongodb['database']]
    api_requests = db[config.mongodb['request_collection']]

    user_requests = api_requests.find({"user": username})
    dashboards = []
    for user_request in user_requests:
        dashboards.append(user_request['name'])

    return dashboards

def load_dashboard_data(username, request_name, context):
    print('init - {}'.format(datetime.now()))
    client = MongoClient(config.mongodb['uri'])
    db = client[config.mongodb['database']]
    api_requests = db[config.mongodb['request_collection']]

    current_request = api_requests.find_one({"name": request_name, "user": username}) 
    print('request - {}'.format(datetime.now()))
    if not current_request:
        context['status'] = 'error'
        context['status_description'] = "The request {} does not exists.".format(request_name)
        return

    if 'active' in current_request:
        context['request_active'] = current_request['active']

    if 'last_pull' in current_request:
        last_refresh = datetime.now() - current_request['last_pull']
        context['last_refresh'] = ''
        if last_refresh.days > 0:
            context['last_refresh'] += str(last_refresh.days)+' day(s), '
        if last_refresh.seconds//3600 > 0:
            context['last_refresh'] += str(last_refresh.seconds//3600)+' hour(s), '
        if (last_refresh.seconds - (last_refresh.seconds//3600)*3600) > 0:
            context['last_refresh'] += str((last_refresh.seconds - (last_refresh.seconds//3600)*3600)//60)+' minute(s) '

        if last_refresh.seconds < 60:
            context['last_refresh'] = 'less than a minute'

        context['last_refresh'] += ' ago'

    print('statistic base data - {}'.format(datetime.now()))
    ## here we pull aggregated data of the last 14 days grouped by day.
    date_query = datetime.today().date() - timedelta(days=14)
    ## match determines the tweets that we want to group
    match = { "$match": { "requests": request_name, "created_at": { "$gte": date_query.isoformat() }}}
    ## transform is necessary to convert DateTime into Date so that MongoDB can group by date instead of datetime
    transform = { "$addFields": { "date": 
                                        { "$dateFromParts": 
                                            { 
                                                "year": { "$year": { "$dateFromString": { "dateString":"$created_at" }}},
                                                "month": { "$month": { "$dateFromString": { "dateString": "$created_at" }}},
                                                "day": { "$dayOfMonth": { "$dateFromString": { "dateString": "$created_at" }}}
                                            }
                                        }
                                    }}
    ## group will sum the information we want
    group = { "$group": {   "_id": "$date", 
                            "totalReplies": {"$sum": "$public_metrics.reply_count" }, 
                            "totalLikes": { "$sum": "$public_metrics.like_count" },
                            "totalRetweets": { "$sum": "$public_metrics.retweet_count"},
                            "totalQuotes": { "$sum": "$public_metrics.quote_count"},
                            "count": { "$sum": 1 } } }
    ## sort the data because why not
    sort = { "$sort": { "_id": -1} }
 
    tweetcollection = db[config.mongodb['tweets_collection']]
    basedata = list(tweetcollection.aggregate([match, transform, group, sort]))

    print('timeline - {}'.format(datetime.now()))
    timeline_data = []
    for entry in basedata:
        new_entry = {}
        new_entry['date'] = entry['_id'].strftime('%Y-%m-%d')
        new_entry['tweets'] = entry['count']
        new_entry['likes'] = entry['totalLikes']
        new_entry['replies'] = entry['totalReplies']
        new_entry['retweets'] = entry['totalRetweets']
        new_entry['quotes'] = entry['totalQuotes']
        timeline_data.append(new_entry)

    context['timeline'] = timeline_data

    print('14 day tweets start - {}'.format(datetime.now()))
    date_query = datetime.today() - timedelta(days=14)
    # prior_date_query = date_query.date() - timedelta(days=14)
    # context['tweets_before_last14days'] = 0
    context['tweets_last14days'] = 0
    context['likes_last14days'] = 0
    context['replies_last14days'] = 0
    context['retweets_last14days'] = 0
    context['quotes_last14days'] = 0

    for entry in basedata:
        if entry['_id'].date() >= date_query.date():
            context['tweets_last14days'] += entry['count']
            context['likes_last14days'] += entry['totalLikes']
            context['replies_last14days'] += entry['totalReplies']
            context['retweets_last14days'] += entry['totalRetweets']
            context['quotes_last14days'] += entry['totalQuotes']        

    # if context['tweets_before_last14days'] > 0:
    #     context['tweets_14day_trend'] = round(context['tweets_last14days'] * 100 / context['tweets_before_last14days']) - 100
    # else:
    #     context['tweets_14day_trend'] = 100

    print('7 day tweets start - {}'.format(datetime.now()))
    date_query = datetime.today() - timedelta(days=7)
    prior_date_query = date_query - timedelta(days=7)
    context['tweets_last7days'] = 0
    context['tweets_before_last7days'] = 0
    context['likes_last7days'] = 0
    context['replies_last7days'] = 0
    context['retweets_last7days'] = 0
    context['quotes_last7days'] = 0

    for entry in basedata:
        if entry['_id'].date() >= date_query.date():
            context['tweets_last7days'] += entry['count']
            context['likes_last7days'] += entry['totalLikes']
            context['replies_last7days'] += entry['totalReplies']
            context['retweets_last7days'] += entry['totalRetweets']
            context['quotes_last7days'] += entry['totalQuotes']

        if (entry['_id'].date() >= prior_date_query.date()) and (entry['_id'].date() < date_query.date()):
            context['tweets_before_last7days'] += entry['count']
    
    if context['tweets_before_last7days'] > 0:
        context['tweets_7day_trend'] = round(context['tweets_last7days'] * 100 / context['tweets_before_last7days']) - 100
    else:
        context['tweets_7day_trend'] = 100    

    print('today tweets starts - {}'.format(datetime.now()))
    date_query = datetime.today()
    prior_date_query = date_query - timedelta(days=1)
    context['tweets_today'] = 0
    context['tweets_yesterday'] = 0
    context['likes_today'] = 0
    context['replies_today'] = 0
    context['retweets_today'] = 0
    context['quotes_today'] = 0

    for entry in basedata:
        if entry['_id'].date() >= date_query.date():
            context['tweets_today'] += entry['count']
            context['likes_today'] += entry['totalLikes']
            context['replies_today'] += entry['totalReplies']
            context['retweets_today'] += entry['totalRetweets']
            context['quotes_today'] += entry['totalQuotes']

        if entry['_id'].date() == prior_date_query.date():
            context['tweets_yesterday'] += entry['count']

    if context['tweets_yesterday'] > 0:
        context['tweets_day_trend'] = round(context['tweets_today'] * 100 / context['tweets_yesterday']) - 100
    else:
        context['tweets_day_trend'] = 100

    print('top10 users start - {}'.format(datetime.now()))
    users = db[config.mongodb['users_collection']]
    # should also be able to filter on actual request-criteria usage
    top_users = list(users.find({"requests.name": request_name}, sort=[("tweet_scores."+request_name, pymongo.DESCENDING)], limit=10))

    for top_user in top_users:
        number_days = datetime.today() - datetime.strptime(top_user['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
        top_user['public_metrics']['average'] = round(top_user['public_metrics']['tweet_count'] / number_days.days, 2)
        top_user['tweet_score'] = top_user['tweet_scores'][request_name]
        for request in top_user['requests']:
            if request['name'] == request_name:
                top_user['current_request'] = {}
                top_user['current_request']['count'] = request['count']
                if not type(request['last_used']) == type(datetime.now()):
                    top_user['current_request']['last_used'] = datetime.strptime(request['last_used'], '%Y-%m-%dT%H:%M:%S.%fZ')
                else:
                    top_user['current_request']['last_used'] = request['last_used']

    context['top10_users'] = top_users

    print('top9 alltime_top_tweets start - {}'.format(datetime.now()))
    top_tweets = list(tweetcollection.find({"requests": request_name}, sort=[("tweet_score", pymongo.DESCENDING)], limit=9))
    context['alltime_top_tweets'] = top_tweets

    print('tagcloud start - {}'.format(datetime.now()))
    tagcloud = []
    tag_stats = list(tweetcollection.aggregate([  
                                                {"$match": { "requests": request_name }},
                                                {"$unwind": "$entities.hashtags"}, 
                                                {"$group": {"_id": { "$toLower": "$entities.hashtags.tag" }, "count": { "$sum": 1 }}},
                                                {"$sort": { "count": -1 } } 
                                             ]))
    highest_count = tag_stats[0]['count'] # MongoDB aggregate function uses decreasing sort
    for tag in tag_stats:
        share = tag['count'] * 100 / highest_count
        if (share > 2) and (tag['_id'].upper() != current_request['hashtag'].upper()):
            tagcloud.append([tag['_id'], share*5])

    context['tagcloud'] = tagcloud

    print('synergy tweets start - {}'.format(datetime.now()))
    synergetic_tweets = list(tweetcollection.find({"requests": request_name, "synergy": {"$ne": 0, "$exists": True}}, sort=[("synergy", pymongo.ASCENDING)], limit=24))
    context['syn_tweets'] = synergetic_tweets

    print('dashboard base data done - {}'.format(datetime.now()))

def main():
    pass

if __name__ == '__main__':
    main()