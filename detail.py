import index
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta

# 今月の予測請求額
def get_estimated_billing(ce, message):
    # 翌日から来月1日までを設定し予測請求額を取得
    next_date = date.today() + timedelta(days=1)
    next_month = date.today() + relativedelta(months=1)
    next_month_first_date = next_month.replace(day=1)

    response = ce.get_cost_forecast(
        TimePeriod={
        'Start': str(next_date),
        'End': str(next_month_first_date)
        },
        Granularity='MONTHLY',
        Metric='UNBLENDED_COST'
    )
    estimated_billing = round(float(response['Total']['Amount']), 2)

    # メッセージ追加
    message.append(f'【今月の予測請求額】\n  ${estimated_billing}')
    return message

# 1日の請求額（前日からの増加額）
def get_daily_billing(ce, today_billing, message):
    first_date = date.today().replace(day=1).isoformat()
    last_date = (date.today() - timedelta(days=1)).isoformat()

    # x月3日~月末のみ前日までの請求額を取得
    if first_date < last_date:
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
        yesterday_billing = {
            'start': response['ResultsByTime'][0]['TimePeriod']['Start'],
            'end': response['ResultsByTime'][0]['TimePeriod']['End'],
            'billing': response['ResultsByTime'][0]['Total']['AmortizedCost']['Amount'],
        }

        # 1日の請求額算出
        daily_billing = round(float(today_billing['billing']) - float(yesterday_billing['billing']), 2)

        # メッセージ追加
        message.append(f'【1日の請求額】\n  ${daily_billing}')
    return message

# サービス毎の請求額
def get_service_billings(ce, message):
    first_date, last_date = index.billing_date()

    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': first_date,
            'End': last_date
        },
        Granularity='MONTHLY',
        Metrics=[
            'AmortizedCost'
        ],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'SERVICE'
            }
        ]
    )

    # サービス名とその請求額を取得
    service_billings = []
    for item in response['ResultsByTime'][0]['Groups']:
        service_billings.append({
            'service_name': item['Keys'][0],
            'billing': item['Metrics']['AmortizedCost']['Amount']
        })

    # メッセージ追加
    yesterday = (date.today() - timedelta(days=1)).strftime('%Y/%m/%d')
    message.append(f'\n【{yesterday}時点の請求額 内訳】')
    for item in service_billings:
        service_name = item['service_name']
        billing = round(float(item['billing']), 2)

        # 請求額が$0の場合は内訳を表示しない
        if billing == 0.0:
            continue
        message.append(f'  ・{service_name}： ${billing}')
    return message