# -*- coding: UTF-8 -*-
'''
compute activeness, influence, importance
first:activeness
     input: uid, geo
second:influence
     input: uid
last: importance
     input: uid, domain, uid
'''
import IP
import sys
import json
import time
import math
import numpy as np
from config import activeness_weight_dict, importance_weight_dict,\
                   domain_weight_dict, topic_weight_dict
reload(sys)
sys.path.append('../../')
from global_utils import redis_cluster, redis_ip, redis_activity
from global_utils import ES_CLUSTER_FLOW1 as es
from global_utils import ES_CLUSTER_FLOW2 as es_cluster
from global_utils import es_user_portrait, es_user_profile, profile_index_name, profile_index_type
from parameter import DAY, WEEK, RUN_TYPE, RUN_TEST_TIME, WORK_TYPE
from time_utils import ts2datetime, datetime2ts

WEEK = 7

#compute activity time max_freq for activeness
#write in version:15-12-08
#input: uid_list
#output: {uid: {'activity_time':x, 'statusnum':y}, ...}
def get_activity_time(uid_list):
    results = {}
    now_ts = time.time()
    now_date = ts2datetime(now_ts)
    #run_type
    if RUN_TYPE == 1:
        timestamp = datetime2ts(now_date)
    else:
        timestamp = datetime2ts("2013-09-08")
    activity_list_dict = {} # {uid:[activity_list], uid:[]}
    for i in range(1,WEEK+1):
        ts = timestamp - DAY*i
        if WORK_TYPE != 0:
            r_result = redis_activity.hmget('activity_'+str(ts), uid_list)
        else:
            r_result = []
            index_name = "activity_" + str(ts2datetime(ts))
            exist_bool = es_cluster.indices.exists(index=index_name)
            if exist_bool:
                es_results = es_cluster.mget(index=index_name, doc_type="activity", body={"ids":uid_list})["docs"]
                for item in es_results:
                    if item['found']:
                        r_result.append(item['_source']['activity_dict'])
                    else:
                        r_result.append(json.dumps({}))
            else:
                r_result = [json.dumps(dict())]*len(uid_list)

        if r_result:
            for j in range(0, len(uid_list)):
                uid = uid_list[j]
                if uid not in activity_list_dict:
                    activity_list_dict[uid] = [0 for i in range(0, 96)]
                user_r_result = r_result[j]
                if user_r_result:
                    user_activity_dict = json.loads(user_r_result)
                    for i in range(0, 96):
                        try:
                            count = user_activity_dict[str(i)]
                        except:
                            count = 0
                        activity_list_dict[uid].append(count)
    for uid in uid_list:
        activity_list = activity_list_dict[uid]
        statusnum = sum(activity_list)
        signal = np.array(activity_list)
        fftResult = np.abs(np.fft.fft(signal))**2
        n = signal.size
        freq = np.fft.fftfreq(n, d=1)
        i = 0
        max_val = 0
        max_freq = 0
        for val in fftResult:
            if val>max_val and freq[i]>0:
                max_val = val
                max_freq = freq[i]
            i += 1
        results[uid] = {'statusnum': statusnum, 'activity_time': math.log(max_freq + 1)}
    
    return results
                        

#use to compute user activeness
#write in version: 15-12-08
#input: user_activeness_geo {geo1:count, geo2:count,...} for the latest dat  ,user_activeness_time {'statusnum':value, 'activity_time':value}
def get_activeness(user_activeness_geo, user_activeness_time):
    result = 0
    # get day geo dict by ip-timestamp result
    max_freq = user_activeness_time['activity_time']
    statusnum = user_activeness_time['statusnum']
    activity_geo_count = len(user_activeness_geo.keys())
    result = activeness_weight_dict['activity_time'] * math.log(max_freq  + 1) + \
             activeness_weight_dict['activity_geo'] * math.log(activity_geo_count + 1) +\
             activeness_weight_dict['statusnum'] * math.log(statusnum + 1)
    return result


#use to get uid_list influence index
#write in version:15-12-08
#input: uid_list
#output: {uid:influence, ...}
def get_influence(uid_list):
    result = {}
    now_ts = time.time()
    #run_type
    if RUN_TYPE == 1:
        now_date = ts2datetime(now_ts - DAY)
    else:
        now_date = ts2datetime(datetime2ts(RUN_TEST_TIME) - DAY)

    index_time = 'bci_' + ''.join(now_date.split('-'))
    index_type = 'bci'
    try:
        es_result = es.mget(index=index_time, doc_type=index_type, body={'ids': uid_list}, _source=False, fields=['user_index'])['docs']
    except Exception, e:
        raise e
    for es_item in es_result:
        uid = es_item['_id']
        if es_item['found'] == True:
            result[uid] = es_item['fields']['user_index'][0]
        else:
            result[uid] = 0

    return result


#use to get user importance
#wirte in version:15-12-08
#input: domain, topic, user_fansnum, fansnum_max for one user
#output: importance
def get_importance(domain, topic, user_fansnum, fansnum_max):
    result = 0
    domain_result = 0
    domain_result = domain_weight_dict[domain]
    topic_result = 0
    topic_list = topic.split('&')
    for topic in topic_list:
        topic_result += topic_weight_dict[topic]
    result = (importance_weight_dict['fansnum']*math.log(float(user_fansnum)/ fansnum_max*9+1, 10) + \
            importance_weight_dict['domain']*domain_result + importance_weight_dict['topic']*(topic_result / 3))*100
    return result

def ip2geo(ip_list):
    ip_list = list(ip_list)
    city_set = set()
    for ip in ip_list:
        try:
            city = IP.find(str(ip))
            if city:
                city.encode('utf-8')
            else:
                city = ''
        except Exception, e:
            city = ''
        if city:
            len_city = len(city.split('\t'))
            if len_city==4:
                city = '\t'.join(city.split('\t')[:2])
            city_set.add(city)
    return list(city_set)

#use to update
def get_activity_geo(uid):
    ip_result = []
    now_ts = time.time()
    now_date = ts2datetime(now_ts)
    ts = datetime2ts(now_date)
    geo_result = {}
    # test
    ts = datetime2ts('2013-09-08')
    for i in range(1,8):
        ts = ts - 24*3600
        r_result = r_cluster.hget('ip_'+str(ts), uid)
        if r_result:
            ip_list = json.loads(r_result).keys()
            ip_result.extend(ip_list)
    ip_list = set(ip_result)
    geo_string = '&'.join(ip2geo(ip_list))
    #print 'geo_string:', geo_string
    return geo_string

#use to update
def get_domain_topic(uid):
    result = dict()
    index_time = 'user_portrait'
    index_type = 'user'
    result = es_user_portrait.get(index=index_time, doc_type=index_type, id=uid)['_source']
    if result:
        #print 'domain, toic:', result['domain'], result['topic']
        return result['domain'], result['topic'] 
    else:
        return None, None



# status: insert or update
# if insert, input info include: uid, domain, topic, activity_geo
# if update, input info include: uid (other information to be got from es)
def get_evaluate_index(user_info, fansnum_max, status='insert'):
    if 'uid' not in user_info:
        return None
    results = dict()
    uid = user_info['uid']
    user_fansnum = user_info['fansnum']
    if status=='insert':
        activity_geo_dict_list = json.loads(user_info['activity_geo'])
        domain = user_info['domain']
        topic = user_info['topic']
        results['activeness'] = get_activeness(uid, activity_geo_dict_list)
        results['influence'] = get_influence(uid)
        results['importance'] = get_importance(uid, domain, topic, user_fansnum, fansnum_max)
    elif status=='update':
        activity_geo_dict_list = json.laods(user_info['activity_geo'])
        results['activeness'] = get_activeness(uid, activity_geo_dict_list)
        results['influence'] = get_influence(uid)
    
    return results


if __name__=='__main__':
    #test_uid_info = {'uid':'2407339403','domain':'domain1 domain2', 'topic':'testtopic', 'activity_geo':'geo&geo'}
    #get_evaluate_index(test_uid_info, 'insert') # status: insert or update
    #get_influence(uid='1978622405')
    #get_activity_geo('1978622405')
    #get_domain_topic('1721131891')
    test_uid_list = ['2845699333', '3203282537']
    result = get_activity_time(test_uid_list)
    print 'activity_result:', result
