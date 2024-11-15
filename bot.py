import ccxt
import dontshare_config
import json
import pandas as pd
import numpy as np
import time
from playsound import playsound
import pytz
import requests

binance = ccxt.binance({
	'apiKey': dontshare_config.xP_KEY,
	'secret': dontshare_config.xP_SECRET,
	'enableRateLimit': True,
	'options': {
		'adjustForTimeDifference': True
	}
});

symbol = 'BTC/USDT';
params = {'postOnly': True};

def round_down(value, decimals):
	factor = 10 ** decimals;
	return int(value*factor)/factor;

# LAY TOTALUSDT O QUA KHU VA SO TIEN DA BO RA
def get_mymoney():
	with open('mymoney.json', 'r') as file:
		data = json.load(file);

	return data['Sotien_danap'], data['VON'], data['old_totalUSDT'], data['sum_USDT_damua'];

# CAP NHAT 
def update_mymoney(VON, old_totalUSDT, sum_USDT_damua):
	with open('mymoney.json', 'r') as file:
		data = json.load(file);

	data['VON'] = VON;
	data['old_totalUSDT'] = old_totalUSDT;
	data['sum_USDT_damua'] = sum_USDT_damua;

	with open('mymoney.json', 'w') as file:
		json.dump(data, file, indent=3);

# LAY SO DU TRONG TAI KHOAN
def get_balance():
	balance = binance.fetch_balance();
	total = balance['total'];
	return total['BTC'], total['USDT'];

# LAY GIA BAN VA GIA MUA
def ask_bid():
	ob = binance.fetch_order_book(symbol);
	ask = ob['asks'][0][0];
	bid = ob['bids'][0][0];

	return ask, bid;

# TINH EMA
def get_ema(data, period):
	return data.ewm(span=period, adjust=False).mean();

# CHECK GIAO DICH CO THANH CONG HAY KHONG
def check_giaodich(delta_USDT, current_time_frame):
	with open("log.txt", "a") as file:
		if (delta_USDT > 0): # Ban thanh cong
			print("$$$ SELL thành công");
			file.write(f"$$$ {current_time_frame} SELL thành công\n");
			playsound('MONEY SOUND.mp3');

			return 1;
		elif (delta_USDT < 0): # Mua thanh cong
			print("$$$ BUY thành công");
			file.write(f"$$$ {current_time_frame} BUY thành công\n");
			playsound('No money.mp3');

			return -1;

		return 0;

# WAVETREND OSCILLATOR (n1 = 10, n2 = 8)
def get_wavetrend(timeframe):
	n1 = 18;
	n2 = 7;

	bars = binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=max(n1, n2) + 50);
	data = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']);
	data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms');
	current_time_frame = data['timestamp'].iloc[-1];

	print(f"~~~ {current_time_frame} Wavetrend Oscillator with timeframe: {timeframe} | n1: {n1} | n2: {n2}");

	data['ap'] = (data['high'] + data['low'] + data['close'])/3;
	data['esa'] = get_ema(data['ap'], n1);
	data['d'] = get_ema(abs(data['ap'] - data['esa']), n1);
	data['ci'] = (data['ap'] - data['esa'])/(0.015*data['d']);
	data['tci'] = get_ema(data['ci'], n2);
	data['wt1'] = data['tci'];
	data['wt2'] = data['wt1'].rolling(window=4).mean();

	return current_time_frame ,data['wt1'], data['wt2'];

# TIN HIEU MUA input(data['wt1'], data['wt2'])
def buy_signal(wt1, wt2, amount, totalbill):
	print(f"xxxxxx WT1 {wt1.iloc[-1]} | WT2 {wt2.iloc[-1]}");
	return amount >= 0.00001 and totalbill >= 5 and wt1.iloc[-1] < -60 and wt1.iloc[-1] > wt1.iloc[-2] and wt1.iloc[-1] > wt2.iloc[-1] and wt1.iloc[-2] < wt2.iloc[-2];

# TIN HIEU BAN
def sell_signal(profit, fee, amount, price, sum_USDT_damua):
	print(f">>>>>> SO SANH {amount*price*(1 - fee)} and {sum_USDT_damua*(1 + profit)}");
	return amount >= 0.00001 and amount*price*(1 - fee) >= sum_USDT_damua*(1 + profit);

# BOT - STRAT: 5m ()
# MUA: dưới -60 and cắt
# BÁN: đủ profit thì bán luôn
def bot():
	with open("log.txt", "a") as file:
		profit = 0.305/100;
		fee = 0.1/100;

		Sotien_danap, VON, old_totalUSDT, sum_USDT_damua = get_mymoney(); # Đã được làm tròn 8 chữ số
		totalcoin, totalUSDT = get_balance(); # Đã được làm tròn 2 chữ số
		available_money = totalUSDT;

		delta_USDT = totalUSDT - old_totalUSDT;
		current_time_frame, wt1_5m, wt2_5m = get_wavetrend('5m');
		current_time_frame, wt1_4h, wt2_4h = get_wavetrend('4h');
		nah = check_giaodich(delta_USDT, current_time_frame);
		if (nah == 1):
			tiendura = delta_USDT*profit;
			delta_USDT -= tiendura;
			sum_USDT_damua = max(0, sum_USDT_damua - delta_USDT*(1 - 0.012/100));

		elif (nah == -1):
			sum_USDT_damua += delta_USDT*(-1);

		ask, bid = ask_bid(); # Đã được làm tròn 2 chữ số
		
		chenhlech = totalUSDT + totalcoin*bid - Sotien_danap;
		print(f"+++ TOTAL BTC_USDT: {totalcoin*bid}({totalcoin} {symbol}) | TOTAL USDT: {totalUSDT} | CHENH LECH: {chenhlech}");
		print(f"++++++ SUM USDT DAMUA: {sum_USDT_damua} | AVAILABLE MONEY: {available_money}");

		print(f">>> ask: {ask}");
		amount = round_down(available_money/ask, 8);
		ask_limit = ask*(1 - 0.02/100);
		totalbill = amount*ask_limit;
		
		print(f"xxx AMOUNT WANT TO BUY: {amount} | TOTALBILL: {totalbill}");
		if (buy_signal(wt1_5m, wt2_5m, amount, totalbill) and buy_signal(wt1_4h, wt2_4h, amount, totalbill)):
			print(f"oooooo Trying to BUY {amount} {symbol}...");
			file.write(f"oooooo {current_time_frame} Trying to BUY {amount} {symbol}...\n");

			try:
				#binance.create_limit_buy_order(symbol, amount, ask_limit, params);
				time.sleep(60);
			except Exception as e:
				print(f"\n\n\n\n\n\nYOUR BUY CODE HAVE SOME ERROR: {e}\n\n\n\n\n\n");
				file.write(f"\n\n\n\n\n\nYOUR BUY CODE HAVE SOME ERROR: {e}\n\n\n\n\n\n");

			try:
				binance.cancel_all_orders(symbol);
				print("ooo Hủy orders cũ thành công!");
			except:
				print("ooo Không có orders cũ để hủy");
		else:
			print(f">>> bid: {bid}");
			bid_limit = bid*(1 + 0.02/100);
			if (sell_signal(profit, fee, totalcoin, bid, sum_USDT_damua)):
				print(f"oooooo Trying to SELL {totalcoin} {symbol}");
				file.write(f"oooooo {current_time_frame} Trying to SELL {totalcoin} {symbol}...\n");

				try:
		 			#binance.create_limit_sell_order(symbol, totalcoin, bid_limit, params);
		 			time.sleep(60);
				except Exception as e:
		 			print(f"\n\n\n\n\nYOUR SELL CODE HAVE SOME ERROR: {e}\n\n\n\n\n\n");
		 			file.write(f"\n\n\n\n\nYOUR SELL CODE HAVE SOME ERROR: {e}\n\n\n\n\n\n");

				try:
		 			binance.cancel_all_orders(symbol);
		 			print("ooo Hủy orders cũ thành công!");
				except:
		 			print("ooo Không có orders cũ để hủy");
		 		
			else:
		 		print("ooo CHILLING");

		update_mymoney(VON, totalUSDT, sum_USDT_damua);

# TRƯỚC KHI CHẠY
# Check lại API và sandbox
# Check lại mymoney.json
# Xóa file log.txt (nếu cần thiết)
run = False;
while (run):
	try:
		print(f"_________ Chuẩn bị lượt trading mới... _________");
		bot();
		print("_________ ĐÂY LÀ THỜI ĐIỂM ĐỂ DỪNG CHƯƠNG TRÌNH _________\n");
	except Exception as e:
		print(f"\n\n\n\n\n\nXXXXXXXXX SOMETHING IS BROKEN OR INTERNET SO SUPID - {e} XXXXXXXXX\n\n\n\n\n\n");

	time.sleep(20);

# ERROR:
# Bị lệch giờ
