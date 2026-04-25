from flask import Flask, render_template, jsonify, request
import requests
import os
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

KMA_API_KEY = os.environ.get('KMA_API_KEY', '')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/degree-days', methods=['POST'])
def get_degree_days():
    data = request.get_json()
    start_date = data.get('startDate')
    station_id = data.get('stationId')
    base_temp = float(data.get('baseTemp', 0))

    if not KMA_API_KEY:
        return jsonify({'error': 'API 키가 설정되지 않았습니다. .env 파일에 KMA_API_KEY를 설정해주세요.'}), 500

    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    except (ValueError, TypeError):
        return jsonify({'error': '날짜 형식이 잘못되었습니다. (YYYY-MM-DD)'}), 400

    end_dt = date.today()

    if start_dt.date() > end_dt:
        return jsonify({'error': '만개일이 오늘 이후일 수 없습니다.'}), 400

    url = 'https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList'
    params = {
        'serviceKey': KMA_API_KEY,
        'pageNo': '1',
        'numOfRows': '999',
        'dataType': 'JSON',
        'dataCd': 'ASOS',
        'dateCd': 'DAY',
        'startDt': start_dt.strftime('%Y%m%d'),
        'endDt': end_dt.strftime('%Y%m%d'),
        'stnIds': station_id,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        resp_data = resp.json()
    except requests.RequestException as e:
        return jsonify({'error': f'기상청 API 요청 실패: {str(e)}'}), 502
    except ValueError:
        return jsonify({'error': '기상청 API 응답을 파싱할 수 없습니다.'}), 502

    body = resp_data.get('response', {}).get('body', {})
    result_code = resp_data.get('response', {}).get('header', {}).get('resultCode', '')
    if result_code != '00':
        result_msg = resp_data.get('response', {}).get('header', {}).get('resultMsg', '알 수 없는 오류')
        return jsonify({'error': f'기상청 API 오류: {result_msg}'}), 502

    items = body.get('items', {})
    if not items or not items.get('item'):
        return jsonify({'error': '해당 기간의 데이터가 없습니다. 날짜 범위나 지점을 확인해주세요.', 'data': []}), 404

    item_list = items['item']
    if isinstance(item_list, dict):
        item_list = [item_list]

    processed = []
    cumulative = 0.0

    for item in item_list:
        avg_temp_val = item.get('avgTa')
        if avg_temp_val is None or avg_temp_val == '':
            avg_temp = None
            dd = 0.0
        else:
            avg_temp = float(avg_temp_val)
            dd = max(0.0, avg_temp - base_temp)

        cumulative += dd
        processed.append({
            'date': item.get('tm', ''),
            'avgTemp': avg_temp,
            'degreeDay': round(dd, 1),
            'cumulative': round(cumulative, 1),
        })

    return jsonify({'data': processed})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
