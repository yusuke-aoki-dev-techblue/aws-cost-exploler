import boto3
import os
import time
from datetime import datetime, timedelta, date
import detail

# 設定日時
def billing_date():
    # 月初の日付取得
    first_date = date.today().replace(day=1).isoformat()
    # 当日の日付取得
    last_date = date.today().isoformat()

    # 今日が1日なら「先月1日から今月1日（今日）」までの範囲にする
    if first_date == last_date:
        last_month_last_date = datetime.strptime(first_date, '%Y-%m-%d') - timedelta(days=1)
        last_month_first_date = last_month_last_date.replace(day=1)
        first_date = last_month_first_date.strftime('%Y-%m-%d')  
    return first_date, last_date

# 請求額取得
def get_billing(ce):
    first_date, last_date = billing_date()

    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': first_date,
            'End': last_date
        },
        Granularity='MONTHLY',
        Metrics=[
            'AmortizedCost'
        ]
    )
    return {
        'start': response['ResultsByTime'][0]['TimePeriod']['Start'],
        'end': response['ResultsByTime'][0]['TimePeriod']['End'],
        'billing': response['ResultsByTime'][0]['Total']['AmortizedCost']['Amount'],
    }

# メッセージ作成
def create_message(total_billing):
    total = round(float(total_billing['billing']), 2)
    sts = boto3.client('sts')
    id_info = sts.get_caller_identity()
    account_id = id_info['Account']
    subject = f'利用料金:${total} AccountID:{account_id}'

    today = datetime.strptime(total_billing['end'], '%Y-%m-%d')
    yesterday = (today - timedelta(days=1)).strftime('%Y/%m/%d')
    message = []
    message.append(f'【{yesterday}時点の請求額】\n  ${total:.2f}')
    return subject, message

# メッセージ送信
def send_message(subject, message_list):
    sns = boto3.client('sns')
    message = '\n'.join(message_list)

    retry_num = 3
    for i in range(retry_num):
        try:
            response = sns.publish(
                TopicArn = os.environ['Topic'],
                Subject = subject,
                Message = message
            )
            break
        # 送信失敗時は2秒後リトライ
        except Exception as e:
            print("送信に失敗しました。リトライ{}/{}".format(i+1, retry_num))
            time.sleep(2)
    return response

# main
def lambda_handler(event, context):
    ce = boto3.client('ce')
    # 請求額取得
    total_billing = get_billing(ce)
    # メッセージ作成
    subject, message = create_message(total_billing)

    ## 拡張用
    ## 今月の予測請求額取得
    message = detail.get_estimated_billing(ce, message)
    ## 1日の請求額（前日からの増加額）
    message = detail.get_daily_billing(ce, total_billing, message)
    ## サービス毎の請求額
    message = detail.get_service_billings(ce, message)

    # メッセージ送信
    send_message(subject, message)