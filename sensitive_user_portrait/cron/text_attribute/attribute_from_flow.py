# -*- coding:utf-8 -*-
import sys
import redis
import IP
import time
import json
from elasticsearch import Elasticsearch

reload(sys)
sys.path.append('./../../')
from global_utils import R_ADMIN as r_sensitive
from global_utils import redis_cluster, redis_ip, redis_activity
from global_utils import ES_CLUSTER_FLOW2 as es_cluster
from global_utils import es_user_profile, es_flow_text,flow_text_index_name_pre, flow_text_index_type
from parameter import  RUN_TYPE, WORK_TYPE,ip_index_pre,MAX_VALUE,\
                       sen_ip_index_pre, act_index_pre, sen_act_index_pre, DAY, sensitive_score_dict
from time_utils import datetime2ts, ts2datetime,ts2date

def ip2geo(ip_dict):
    city_set = set()
    geo_dict = dict()
    for ip in ip_dict:
        try:
            city = IP.find(str(ip))
            if city:
                city.encode('utf-8')
            else:
                city=''
        except Exception, e:
            city = ''
        if city:
            len_city = len(city.split('\t'))
            if len_city == 4:
                city = '\t'.join(city.split('\t')[0:3])
            try:
                geo_city[city] += ip_dict[ip]
            except:
                geo_dict[city] = ip_dict[ip]
    return geo_dict

def extract_geo(result):
    geo_string = ''
    date_list = result.values()
    result_dict = {}
    result_list = []
    for item in date_list:
        result_dict.update(ip2geo(item))
    for geo in result_dict:
        result_list.append(geo.split('\t')[-1])
    geo_string = '&'.join(list(set(result_list)))
    return geo_string

def ip_to_geo(result):
    date_list = result.values()
    result_dict = {}
    for item in result:
        result_dict.update({item:ip2geo(result[item])})
    return result_dict

def extract_string(result):
    result_string = ''
    date_list = result.values()
    result_list = []
    for item in date_list:
        result_list.extend(item.keys())
    result_string = '&'.join(list(set(result_list)))
    return result_string

# hashtag activity_geo ip sensitive_words
def get_flow_information(uid_list):
    # 前七天的数据, 不能用于每天更新
    lenth = len(uid_list)
    results = {}
    iter_results = {}
    result_dict = {}
    if RUN_TYPE:
        now_ts = time.time()
        now_date = ts2datetime(now_ts) # date: 2013-09-01
    else:
        now_date = "2013-09-08"
    ts = datetime2ts(now_date)

    start_ts = ts - 8*3600*24
    for i in range(1,8):
        ts = start_ts + i*3600*24
        date = ts2datetime(ts)
        print "date:", date
        uid_day_geo = {}
        sensitive_uid_day_geo = {}
        flow_index_name = flow_text_index_name_pre + str(date)
        # hashtag
        print uid_list
        hashtag_results = redis_cluster.hmget('hashtag_'+str(ts), uid_list)
        sensitive_hashtag = redis_cluster.hmget('sensitive_hashtag_'+str(ts), uid_list)
        # sensitive_words
        sensitive_results = redis_cluster.hmget('sensitive_'+str(ts), uid_list)
        # ip
        if WORK_TYPE == 0:
            ip_index_name = ip_index_pre + str(date)
            sensitive_ip_index_name = sen_ip_index_pre + str(date)
            #activity_index_name = act_index_pre + str(date)
            #sensitive_activity_index_name = sen_act_index_pre + str(date)
            exist_bool = es_cluster.indices.exists(index=ip_index_name)
            sensitive_exist_bool = es_cluster.indices.exists(index=sensitive_ip_index_name)
            #activity_exist_bool = es_cluster.indices.exists(index=activity_index_name)
            #sensitive_activity_exist_bool = es_cluster.indices.exists(index=sensitive_activity_index_name)
            if exist_bool:
                ip_results = es_cluster.mget(index=ip_index_name, doc_type="ip", body={"ids":uid_list})["docs"]
            else:
                ip_results = [dict()]*lenth
            if sensitive_exist_bool:
                sensitive_ip_results = es_cluster.mget(index=sensitive_ip_index_name, doc_type="sensitive_ip", body={"ids":uid_list})["docs"]
            else:
                sensitive_ip_results = [dict()]*lenth
            """
            if activity_exist_bool:
                activity_results = es_cluster.mget(index=activity_index_name, doc_type="activity", body={"ids":uid_list})["docs"]
            else:
                activity_results = [dict()]*lenth
            if sensitive_activity_exist_bool:
                sensitive_activity_results = es_cluster.mget(index=sensitive_activity_index_name, doc_type="sensitive_activity", body={"ids":uid_list})["docs"]
            else:
                sensitive_activity_results = [dict()]*lenth
            """
        else:
            ip_results = redis_ip.hmget('ip_'+str(ts), uid_list)
            sensitive_ip_results = redis_ip.hmget('sensitive_ip_'+str(ts), uid_list)
            #activity_results = redis_activity.hmget('activity_'+str(date), uid_list)
            #sensitive_activity_results = redis_activity.hmget('sensitive_activity_'+str(date), uid_list)

        for j in range(0, len(uid_list)):
            uid = uid_list[j]
            if uid not in iter_results:
                iter_results[uid] = {'hashtag':{}, 'sensitive_hashtag':{}, 'geo':{}, "sensitive_geo":{},'geo_track':[],'keywords':{}, \
                        'sensitive_words':{}, "sensitive_geo_track":[],'ip': [], 'sensitive_ip':[]}
            # sensitive words
            if sensitive_results[j]:
                sensitive_words_results = json.loads(sensitive_results[j])
                for sensitive_word in sensitive_words_results:
                    try:
                        iter_results[uid]["sensitive_words"][sensitive_word] += sensitive_words_results[sensitive_word]
                    except:
                        iter_results[uid]["sensitive_words"][sensitive_word] = sensitive_words_results[sensitive_word]
            #print "sensitive_words:", iter_results[uid]["sensitive_words"]

            if hashtag_results[j]:
                hashtag_dict = json.loads(hashtag_results[j])
                for hashtag in hashtag_dict:
                    try:
                        iter_results[uid]['hashtag'][hashtag] += hashtag_dict[hashtag]
                    except:
                        iter_results[uid]['hashtag'][hashtag] = hashtag_dict[hashtag]
            #print "hashtag: ", iter_results[uid]['hashtag']

            if sensitive_hashtag[j]:
                sensitive_hashtag_dict = json.loads(sensitive_hashtag[j])
                for hashtag in sensitive_hashtag_dict:
                    try:
                        iter_results[uid]['sensitive_hashtag'][hashtag] += sensitive_hashtag_dict[hashtag]
                    except:
                        iter_results[uid]['sensitive_hashtag'][hashtag] = sensitive_hashtag_dict[hashtag]
            #print "sensitive_hashtag:", iter_results[uid]['sensitive_hashtag']

            uid_day_geo[uid] = {}
            sensitive_uid_day_geo[uid] = {}
            if WORK_TYPE == 0:# es
                if ip_results[j]:
                    if ip_results[j]['found']:
                        detail_item = ip_results[j]['_source']
                        ip_dict = json.loads(detail_item['ip_dict'])
                    else:
                        ip_dict = {}
                else:
                    ip_dict = {}
            else:
                if ip_results[j]:
                    ip_dict = json.loads(ip_results[j])
                else:
                    ip_dict = {}
            if ip_dict:
                #iter_results[uid]['ip'].append(ip_dict)
                geo_dict = ip2geo(ip_dict)
                for geo, count in geo_dict.iteritems():
                    try:
                        iter_results[uid]['geo'][geo] += count
                    except:
                        iter_results[uid]['geo'][geo] = count
                    try:
                        uid_day_geo[uid][geo] += count
                    except:
                        uid_day_geo[uid][geo] = count
            #iter_results[uid]['ip'].append(ip_dict)
            iter_results[uid]['geo_track'].append(uid_day_geo[uid])
            #print "ip:", iter_results[uid]['ip'], iter_results[uid]['geo_track']

            if WORK_TYPE == 0:
                if sensitive_ip_results[j]:
                    if sensitive_ip_results[j]['found']:
                        detail_item = sensitive_ip_results[j]['_source']
                        sensitive_ip_dict = json.loads(detail_item['sensitive_ip_dict'])
                    else:
                        sensitive_ip_dict = dict()
                else:
                    sensitive_ip_dict = dict()
            else:
                if sensitive_ip_results[j]:
                    sensitive_ip_dict = json.loads(sensitive_ip_results[j])
                else:
                    sensitive_ip_dict = dict()
            if sensitive_ip_dict:
                sensitive_geo_dict = ip2geo(sensitive_ip_dict)
                #iter_results[uid]['sensitive_ip'].append(sensitive_ip_dict)
                for geo, count in sensitive_geo_dict.iteritems():
                    try:
                        iter_results[uid]['sensitive_geo'][geo] += count
                    except:
                        iter_results[uid]['sensitive_geo'][geo] = count
                    try:
                        sensitive_uid_day_geo[uid][geo] += count
                    except:
                        sensitive_uid_day_geo[uid][geo] = count
            #iter_results[uid]['sensitive_ip'].append(sensitive_ip_dict)
            iter_results[uid]['sensitive_geo_track'].append(sensitive_uid_day_geo[uid])
            #print "sensitive_ip:", iter_results[uid]['sensitive_ip'], iter_results[uid]['sensitive_geo_track']

        # compute keywords
        flow_text_exist = es_flow_text.indices.exists(index=flow_index_name)
        if flow_text_exist:
             text_results = es_flow_text.search(index=flow_index_name, doc_type=flow_text_index_type,\
                    body={'query':{'filtered':{'filter':{'terms':{'uid': uid_list}}}}, 'size':MAX_VALUE},_source=False, fields=['uid', 'keywords_dict'])['hits']['hits']
        else:
            text_results = {}
        for item in text_results:
            uid = item['fields']['uid'][0]
            uid_keywords_dict = json.loads(item['fields']['keywords_dict'][0])
            for keywords in uid_keywords_dict:
                try:
                    iter_results[uid]['keywords'][keywords] += uid_keywords_dict[keywords]
                except:
                    iter_results[uid]['keywords'][keywords] = uid_keywords_dict[keywords]
        #print "keywords:", iter_results[uid]['keywords']

    for uid in uid_list:
        results[uid] = {}
        # hashtag
        hashtag_dict = iter_results[uid]['hashtag']
        results[uid]['hashtag_dict'] = json.dumps(hashtag_dict)
        results[uid]['hashtag_string'] = '&'.join(hashtag_dict.keys())
        # sensitive hashtag
        sensitive_hashtag_dict = iter_results[uid]['sensitive_hashtag']
        results[uid]['sensitive_hashtag_dict'] = json.dumps(sensitive_hashtag_dict)
        results[uid]['sensitive_hashtag_string'] = '&'.join(sensitive_hashtag_dict.keys())
        # sensitive_words
        sensitive_word_dict = iter_results[uid]['sensitive_words']
        results[uid]['sensitive_words_dict'] = json.dumps(sensitive_word_dict)
        results[uid]['sensitive_words_string'] = '&'.join(sensitive_word_dict.keys())
        sensitive_score = 0
        for k,v in sensitive_word_dict.iteritems():
            tmp = r_sensitive.hget('sensitive_words', k)
            if tmp:
                tmp_stage = json.loads(tmp)
                sensitive_score += sensitive_score_dict[str(tmp_stage[0])]*v
        results[uid]['sensitive'] = sensitive_score
        # geo
        geo_dict = iter_results[uid]['geo']
        geo_track_list = iter_results[uid]['geo_track']
        results[uid]['activity_geo_dict'] = json.dumps(geo_track_list)
        geo_dict_keys = geo_dict.keys()
        results[uid]['activity_geo'] = '&'.join(['&'.join(item.split('\t')) for item in geo_dict_keys])
        results[uid]['activity_geo_aggs'] = '&'.join([item.split('\t')[-1] for item in geo_dict_keys])
        sensitive_geo_dict = iter_results[uid]['sensitive_geo']
        sensitive_geo_track_list = iter_results[uid]['sensitive_geo_track']
        results[uid]['sensitive_activity_geo_dict'] = json.dumps(sensitive_geo_track_list)
        sensitive_geo_dict_keys = sensitive_geo_dict.keys()
        results[uid]['sensitive_activity_geo'] = '&'.join(['&'.join(item.split('\t')) for item in sensitive_geo_dict_keys])
        results[uid]['sensitive_activity_geo_aggs'] = '&'.join([item.split('\t')[-1] for item in sensitive_geo_dict_keys])

        keywords_dict = iter_results[uid]['keywords']
        keywords_top50 = sorted(keywords_dict.items(), key=lambda x:x[1], reverse=True)[:50]
        keywords_top50_string = '&'.join([keyword_item[0] for keyword_item in keywords_top50])
        results[uid]['keywords_dict'] = json.dumps(keywords_top50)
        results[uid]['keywords_string'] = keywords_top50_string

    return results


# update attribute

def update_day_hashtag(uid_list):
    results = {}
    all_results = {}
    now_ts = time.time()
    if RUN_TYPE == 1:
        now_date_ts = datetime2ts(ts2datetime(now_ts))
    else:
        now_date_ts = datetime2ts('2013-09-02')

    for i in range(WEEK,0,-1):
        ts = now_date_ts - DAY*i
        count = 0
        hashtag_results = redis_cluster.hmget('hashtag_'+str(ts), uid_list)
        for uid in uid_list:
            if uid not in results:
                results[uid] = {}
            hashtag_item = hashtag_results[count]
            if hashtag_item:
                hashtag_dict = json.loads(hashtag_item)
            else:
                hashtag_dict = {}
            for hashtag in hashtag_dict:
                try:
                    results[uid][hashtag] += 1
                except:
                    results[uid][hashtag] = 1
            count += 1

    for uid in uid_list:
        user_hashtag_dict = results[uid]
        hashtag_string = '&'.join(user_hashtag_dict.keys())
        all_results[uid] = {'hashtag_string': hashtag_string, 'hashtag_dict':json.dumps(user_hashtag_dict)}

    return all_results


def update_day_sensitive_hashtag(uid_list):
    results = {}
    all_results = {}
    now_ts = time.time()
    if RUN_TYPE == 1:
        now_date_ts = datetime2ts(ts2datetime(now_ts))
    else:
        now_date_ts = datetime2ts('2013-09-02')

    for i in range(WEEK,0,-1):
        ts = now_date_ts - DAY*i
        count = 0
        hashtag_results = redis_cluster.hmget('sensitive_hashtag_'+str(ts), uid_list)
        for uid in uid_list:
            if uid not in results:
                results[uid] = {}
            hashtag_item = hashtag_results[count]
            if hashtag_item:
                hashtag_dict = json.loads(hashtag_item)
            else:
                hashtag_dict = {}
            for hashtag in hashtag_dict:
                try:
                    results[uid][hashtag] += 1
                except:
                    results[uid][hashtag] = 1
            count += 1

    for uid in uid_list:
        user_hashtag_dict = results[uid]
        hashtag_string = '&'.join(user_hashtag_dict.keys())
        all_results[uid] = {'sensitive_hashtag_string': hashtag_string, 'sensitive_hashtag_dict':json.dumps(user_hashtag_dict)}

    return all_results


#update geo
def update_day_geo(uid_list, user_info_list):
    results = {}
    now_ts = time.time()
    if RUN_TYPE == 1:
        now_date_ts = datetime2ts(ts2datetime(now_ts))
    else:
        now_date_ts = datetime2ts('2013-09-02')
    now_date = ts2datetime(now_date_ts)

    if WORK_TYPE == 0:
        if es_cluster.indices.exists(index="ip_"+str(now_date)):
            ip_results = es_cluster.mget(index="ip_"+str(now_date), doc_type="ip", body={"ids":uid_list})['docs']
        else:
            ip_results = [json.dumps({})]*len(uid)
        if es_cluster.indices.exists(index="sensitive_ip_"+str(now_date)):
            sensitive_ip_results = es_cluster.mget(index="sensitive_ip_"+str(now_date), doc_type="sensitive_ip", body={"ids":uid_list})["docs"]
        else:
            sensitive_ip_results = [{"found":False}]*len(uid)
    else:
        ip_results = redis_ip.mget("ip_"+str(now_date_ts), uid_list)
        sensitive_ip_results = redis_ip.mget('sensitive_ip_'+str(now_date_ts), uid_list)


    count = 0
    for uid in uid_list:
        if uid not in results:
            results[uid] = {'activity_geo':{}, 'activity_geo_dict':[]}
            results[uid] = {'sensitive_activity_geo':{}, 'sensitive_activity_geo_dict':[]}
        uid_ip_results = ip_results[count]
        uid_sensitive_ip_results = sensitive_ip_results[count]
        if WORK_TYPE == 0:
            if uid_ip_results['found']:
                uid_ip_dict = json.loads(uid_ip_results['_source']['ip_dict'])
            else:
                uid_ip_dict = {}
            if sensitive_uid_ip_results['found']:
                sensitive_uid_ip_dict = json.loads(sensitive_uid_ip_results['_source']['sensitive_ip_dict'])
            else:
                sensitive_uid_ip_dict = {}
        else:
            if uid_ip_results:
                uid_ip_dict = json.loads(uid_ip_results)
            else:
                uid_ip_dict = {}
            if uid_sensitive_ip_results:
                sensitive_uid_ip_dict = json.loads(sensitive_uid_ip_results)
            else:
                sensitive_uid_ip_dict = {}
        day_results = {}
        sensitive_day_results = {}
        if uid_ip_dict:
            #iter_results[uid]['ip'].append(ip_dict)
            geo_dict = ip2geo(uid_ip_dict)
            for geo, count in geo_dict.iteritems():
                try:
                    day_results[geo] += count
                except:
                    day_results[geo] = count
        if sensitive_uid_ip_dict:
            #iter_results[uid]['ip'].append(ip_dict)
            geo_dict = ip2geo(sensitive_uid_ip_dict)
            for geo, count in geo_dict.iteritems():
                try:
                    sensitive_day_results[geo] += count
                except:
                    sensitive_day_results[geo] = count
        #update the activity_geo_dict
        activity_geo_history_list = json.loads(user_info_list[uid]['activity_geo_dict'])
        sensitive_activity_geo_history_list = json.loads(user_info_list[uid]['activity_geo_dict'])
        activity_geo_history_list.append(day_results)
        sensitive_activity_geo_history_list.append(sensitive_day_results)
        results[uid]['activity_geo_dict'] = json.dumps(activity_geo_history_list[-30:])
        results[uid]['sensitive_activity_geo_dict']=json.dumps(sensitive_activity_geo_history_list[-30:])

        #update the activity_geo
        week_activity_geo_list = activity_geo_history_list[-7:]
        sensitive_week_activity_geo_list = sensitive_activity_geo_history_list[-7:]
        week_geo_list = []
        sensitive_week_geo_list = []
        for activity_geo_item in week_activity_geo_list:
            geo_list = activity_geo_item.keys()
            week_geo_list.extend(geo_list)
        for activity_geo_item in sensitive_week_activity_geo_list:
            geo_list = activity_geo_item.keys()
            sensitive_week_geo_list.extend(geo_list)
        week_geo_list = list(set(week_geo_list))
        sensitive_week_geo_list = list(set(sensitive_week_geo_list))
        week_geo_string = '&'.join(['&'.join(item.split('\t')) for item in week_geo_list])
        sensitive_week_geo_string = '&'.join(['&'.join(item.split('\t')) for item in sensitive_week_geo_list])
        try:
            week_geo_aggs_string = '&'.join([item.split('\t')[-1] for item in week_geo_list])
        except:
            week_geo_aggs_string = ''
        try:
            sensitive_week_geo_aggs_string = '&'.join([item.split('\t')[-1] for item in sensitive_week_geo_list])
        except:
            sensitive_week_geo_aggs_string = ''

        results[uid]['activity_geo'] = week_geo_string
        results[uid]['activity_geo_aggs'] = week_geo_aggs_string
        results[uid]['sensitive_activity_geo'] = sensitive_week_geo_string
        results[uid]['sensitive_activity_geo_aggs'] = sensitive_week_geo_aggs_string

    #print 'update geo results:', results
    return results


def update_day_activeness(geo_results, user_info_list):
    results = {}
    uid_list = user_info_list.keys()
    activity_time_results = get_activity_time(uid_list)
    count = 0
    for uid in uid_list:
        results[uid] = {}
        activity_geo_dict = json.loads(geo_results[uid]['activity_geo_dict'])[-1]
        geo_count = len(activity_geo_dict)
        max_freq = activity_time_results[uid]['activity_time']
        statusnum = activity_time_results[uid]['statusnum']
        day_activeness = activeness_weight_dict['activity_time'] * math.log(max_freq + 1) +\
                activeness_weight_dict['activity_geo'] * math.log(geo_count + 1) + \
                activeness_weight_dict['statusnum'] * math.log(statusnum + 1)
        results[uid] = {'activeness':day_activeness}

    return results

def update_day_influence(uid_list, user_info_list):
    results = {}
    day_influence_results = get_influence(uid_list)
    for uid in uid_list:
        day_influence = day_influence_results[uid]
        results[uid] = {'influence': day_influence}
    return results


def update_day_sensitive(uid_list):
    results = {}
    for uid in uid_list:
        results[uid] = {"sensitive": 0, 'sensitive_string': "", 'sensitive_dict': json.dumps({})}
    all_results = {}
    now_ts = time.time()
    if RUN_TYPE == 1:
        now_date_ts = datetime2ts(ts2datetime(now_ts))
    else:
        now_date_ts = datetime2ts('2013-09-03')
    today_sensitive_dict = {}
    sensitive_results = redis_cluster.hmget("sensitive_"+str(now_date_ts), uid_list)
    for item in sensitive_results:
        for uid, words_dict in item.iteritems():
            sensitive_index = 0
            sensitive_words_dict = {}
            if words_dict:
                sensitive_words_dict = json.dumps(words_dict)
                for word, count in words_dict.iter_items():
                    tmp_stage = r_sensitive.hget("sensitive_words", word)
                    if tmp_stage:
                        tmp = json.loads(tmp_stage)
                        sensitive_index += sensitive_score_dict[tmp[0]] * count
            sensitive_words_string = "&".join(sensitive_words_dict.keys())
            results[uid] = {'sensitive': sensitive_index, "sensitive_words_string":sensitive_words_string, "sensitive_words_dict":sensitive_words_dict}

    return results

def update_day_profile(uid_list):
    result_dict = dict()
    try:
        bci_history_result = es_bci_history.mget(index=bci_history_index_name, doc_type=bci_history_index_type, body={'ids':uid_list}, fields=['user_fansnum', 'weibo_month_sum', 'user_friendsnum'])['docs']
    except:
        bci_history_result = []
    iter_count = 0
    for uid in uid_list:
        try:
            bci_history_item = bci_history_result[iter_count]
        except:
            bci_history_item = {}
        if bci_history_item and bci_history_item['found']==True:
            if isinstance(bci_history_item['fields']['weibo_month_sum'][0], int):
                statusnum = bci_history_item['fields']['weibo_month_sum'][0]
            else:
                statusnum = 0
            if isinstance(bci_history_item['fields']['user_fansnum'][0], int):
                fansnum = bci_history_item['fields']['user_fansnum'][0]
            else:
                fansnum = 0
            if isinstance(bci_history_item['fields']['user_friendsnum'][0], int):
                friendsnum = bci_history_item['fields']['user_friendsnum'][0]
            else:
                friendsnum = 0
        else:
            statusnum = 0
            fansnum = 0
            friendsnum = 0

        result_dict[uid] = {'statusnum': statusnum, 'fansnum':fansnum, 'friendsnum': friendsnum}
        iter_count += 1

    return result_dict

def save_bulk_action(uid_list, hashtag_results, geo_results, activeness_results, influence_results, sensitive_results, profile_results):
    bulk_action = []
    for uid in uid_list:
        user_results = {}
        user_results = dict(user_results, **hashtag_results[uid])
        user_results = dict(user_results, **sensitive_hashtag_results[uid])
        user_results = dict(user_results, **geo_results[uid])
        user_results = dict(user_results, **activeness_results[uid])
        user_results = dict(user_results, **influence_results[uid])
        user_results = dict(user_results, **sensitive_results[uid])
        user_results = dict(user_results, **profile_results[uid])
        user_results['update_day'] = ts2datetime(time.time())
        action = {'update':{'_id': uid}}
        bulk_action.extend([action, {'doc': user_results}])

    es_user_portrait.bulk(bulk_action, index=portrait_index_name, doc_type=portrait_index_type)


def update_attribute_day():
    bulk_action = []
    count = 0
    user_info_list = {}
    start_ts = time.time()
    while True:
        r_user_info = update_day_redis.rpop(UPDATE_DAY_REDIS_KEY)
        if r_user_info:
            r_user_info = json.loads(r_user_info)
            user_info_list[uid] = r_user_info[uid]
            count += 1
        else:
            break

        if count % 100==0:
            uid_list = user_info_list.keys()
            #get user_list hashtag_results
            hashtag_results = update_day_hashtag(uid_list)
            #get user geo today
            geo_results = update_day_geo(uid_list, user_info_list)
            #get user activeness evaluate
            activeness_results = update_day_activeness(geo_results, user_info_list)
            #get user influence
            influence_results = update_day_influence(uid_list, user_info_list)
            #get user sensitive
            sensitive_results = update_day_sensitive(uid_list)
            #print 'sensitive_results:', sensitive_results
            profile_results = update_day_profile(uid_list)
            #update to es by bulk action
            save_bulk_action(uid_list, hashtag_results, geo_results, activeness_results, influence_results, sensitive_results, profile_results)
            user_info_list = {}
            end_ts = time.time()
            print '%s sec count 1000' % (end_ts - start_ts)
            start_ts = end_ts

    if user_info_list != {}:
        uid_list = user_info_list.keys()
        #get user_list hashtag_results
        hashtag_results = update_day_hashtag(uid_list)
        #get user geo today
        geo_results = update_day_geo(uid_list, user_info_list)
        #get user activeness evaluate
        activeness_results = update_day_activeness(geo_results, user_info_list)
        #get user influence
        influence_results = update_day_influence(uid_list, user_info_list)
        #get user sensitive
        sensitive_results = update_day_sensitive(uid_list)
        #print 'sensitive_results:', sensitive_results
        profile_results = update_day_profile(uid_list)
        #update to es by bulk action
        save_bulk_action(uid_list, hashtag_results, geo_results, activeness_results, influence_results, sensitive_results, profile_results)


if __name__ == '__main__':
    test_uid = ['2112067715', '3356923604']
    result = get_flow_information(test_uid)
    print result





if __name__ == '__main__':
    test_uid = ['2112067715', '3356923604']
    result = get_flow_information(test_uid)
    print result
