#!/usr/bin/python
# -*- coding: utf_8 -*-

'''
Скрипт для автоматизации тачки
!!!
Внимание!
Данный скрипт предоставляется исключительно в информационных целях.
Автор не несет никакой ответственности за результаты использования.
Любые риски являются вашими.
!!!

Как использовать:
1. В интернет банке нужно создать 2 шаблона переводов(карта->вклад и вклад->карта)
имена этих шаблонов нужно подсовывать скрипту в параметр --template

2. Нужно запретить доступ на сайт касперского, которому не нравится 
что в интернет банк пытается зайти безголовый браузер
самый простой вариант - дописать в hosts следующую строку:
127.0.0.1       ru.fp.kaspersky-labs.com


Примеры:
--показ баланса
touch.py --debug --login mylogin --pass mypass --cmd card-balance
touch.py --debug --login mylogin --pass mypass --cmd hold-balance

--перевод всего с карты на вклад
touch.py --debug --login mylogin --pass mypass --cmd transfer --template mytemplate_c2h --amount all-from-card

--перевод 100рублей по указанному шаблону
touch.py --debug --login mylogin --pass mypass --cmd transfer --template mytemplate_h2c --amount 100
'''

import signal
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.action_chains import ActionChains
import logging
import argparse


maxattempts = 15			# количество попыток
delay_first = 10			# задержка ожидания завершения загрузки страницы в секундах
delay_amp = 3				# увеличиваем задержку для каждой следующей попытки
DEBUG_LOG_DIR = './'		# каталог для отладочных скриншутов
log_file = '/var/log/touchbank.log'	# лог файл
ua = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:47.0) Gecko/20100101 Firefox/47.0"
ua = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:49.0) Gecko/20100101 Firefox/49.0'



# логгер
def set_logger(logger_name, level):
	logger = logging.getLogger(logger_name)
	hdlr = logging.FileHandler(log_file)
	formatter = logging.Formatter('%(asctime)s (%(name)s) %(levelname)s %(message)s')
	hdlr.setFormatter(formatter)
	logger.addHandler(hdlr)
	if level == logging.DEBUG:
		logger.addHandler(logging.StreamHandler()) # вывод на экран
	logger.setLevel(level)
	return logger

def set_parser():
	parser = argparse.ArgumentParser(description='Touchbank automation software')
	parser.add_argument('--cmd', required=True, type=str, metavar='command', 
		help='Command name transfer|card-balance|hold-balance', dest='cmd')
	parser.add_argument('--login', required=True, type=str, metavar='login', 
		help='Login', dest='login')
	parser.add_argument('--pass', required=True, type=str, metavar='password', 
		help='Password', dest='password')
	parser.add_argument('--template', required=False, type=str, metavar='template', 
		help='Transfer template name', dest='template', default=False)
	parser.add_argument('--amount', required=False, type=str, metavar='amount', 
		help='Transfer amount: float|all-from-card|all-from-hold', dest='amount', default=False)
	parser.add_argument('--debug', required=False, action='store_true', 
		help='Debug mode', dest='debug', default=False)
	return parser.parse_args()


class Touchbank():
	
	driver = None
	_debug = None
	_login = None
	_password = None
	commands = None
	
	def __init__(self, login=None, password=None, delay=10, logger=None, debug=None):
		dcap = dict(DesiredCapabilities.PHANTOMJS)
		dcap["phantomjs.page.settings.userAgent"] = (ua)
		self.driver = webdriver.PhantomJS(
			desired_capabilities=dcap, 
			# каталог в котором лежит phantomjs, если его нет в PATH
			# node тоже должен быть в PATH
			#executable_path='./node_modules/phantomjs/bin/phantomjs',
			#executable_path='/home/user/.nvm/versions/node/v6.6.0/bin/phantomjs',
		)
		self.driver.set_window_size(1024, 768)
		self._debug = debug
		self._login = login
		self._password = password
		self._delay = delay
		self._logger = logger

		# логинимся
		logger.debug('Trying to log in...')
		self.driver.get('https://www.touchbank.com/lk')
		time.sleep(self._delay)
		actions = ActionChains(self.driver)
		actions.send_keys(Keys.TAB + self._login + Keys.TAB + self._password + Keys.ENTER)
		actions.perform()
		logger.info('Logged in!')
		if self._debug: 
			self.driver.save_screenshot(DEBUG_LOG_DIR+'login.png')

	def __del__(self):
		self.driver.service.process.send_signal(15) #signal.SIGTERM
		self.driver.quit()
	
	def get_card_balance(self):
		logger.debug('Getting card balance...')
		self.driver.get('https://www.touchbank.com/lk/cards')
		time.sleep(self._delay)
		if self._debug:
			self.driver.save_screenshot(DEBUG_LOG_DIR+'cards.png')
		# ищем элемент, чистим
		element = self.driver.find_element(By.XPATH, '//p[contains(@class, "cards-amount")]')
		text = re.sub(r'[^\d,\w]', '', element.text)
		m = re.search(r'(\d+,\d\d)(RUR|USD|/EUR)', text)
		balance = m.group(1)
		currency = m.group(2)
		balance = float(balance.replace(',', '.'))
		logger.debug('Found card balance: %f' % balance)
		return {'balance': balance, 'currency': currency}

	def get_hold_balance(self):
		logger.debug('Getting holdings balance...')
		self.driver.get('https://www.touchbank.com/lk/holdings')
		time.sleep(self._delay)
		if self._debug:
			self.driver.save_screenshot(DEBUG_LOG_DIR+'holdings.png')
		# ищем элемент, чистим
		element = self.driver.find_element(By.XPATH, '//text()[. = "Текущий баланс"]/parent::h4/parent::div/h1/em')
		text = re.sub(r'[^\d,\w]', '', element.text)
		m = re.search(r'(\d+,\d\d)(RUR|USD|/EUR)', text)
		balance = m.group(1)
		currency = m.group(2)
		balance = float(balance.replace(',', '.'))
		logger.debug('Found holdings balance: %f' % balance)
		return {'balance': balance, 'currency': currency}

	def transfer(self, amount=None, template=None):
		# проверка параметров
		if (not amount or \
			not template or \
			not (isinstance(amount, float) or isinstance(amount, int)) or \
			not isinstance(template, str)):
			raise ValueError("Need parameters: amount(float), template(str)")
		logger.debug('Making transfer with template: %s...' % template)
		# переход на страницу с шаблонами
		logger.debug('Going to templates page...')
		self.driver.get('https://www.touchbank.com/lk/transactions/templates')
		time.sleep(self._delay)
		if self._debug:
			self.driver.save_screenshot(DEBUG_LOG_DIR+'transfer_templates.png')
		# ищем элемент с нужным шаблоном и кликаем по нему
		logger.debug('Clicking on template...')
		template_link = self.driver.find_element(By.XPATH, '//text()[. = "%s"]/parent::a' % template)
		template_link.click()
		time.sleep(self._delay)
		if self._debug:
			self.driver.save_screenshot(DEBUG_LOG_DIR+'transfer_1.png')
		# ищем поле ввода суммы, вводим сумму и жмем enter
		logger.debug('Filling amount...')
		amount_input = self.driver.find_element(By.XPATH, '//input[@name="amount"]')
		amount_input.send_keys(Keys.BACKSPACE*10 + str(amount))
		if self._debug:
			self.driver.save_screenshot(DEBUG_LOG_DIR+'transfer_2.png')
		amount_input.send_keys(Keys.ENTER)
		time.sleep(self._delay * 2)
		# проверяем результат
		logger.debug('Checking transfer result...')
		if self._debug:
			self.driver.save_screenshot(DEBUG_LOG_DIR+'transfer_3.png')
		try:
			confirm = self.driver.find_element(By.XPATH, '//legend[contains(@class, "ib-form-legend_success")]')
		except NoSuchElementException:
			logger.error("Transfer was NOT successfull")
			raise ValueError("Transfer was NOT successfulls")
		else:
			logger.info("Transfer was successfull")
			return True
		

if __name__=='__main__':
	
	cmd_args = set_parser()
	if cmd_args.debug:
		logger = set_logger('touchbank', logging.DEBUG)
	else:
		logger = set_logger('touchbank', logging.INFO)
	
	attempt = 1
	delay = delay_first
	while(attempt <= maxattempts):
		logger.debug("Attempt: [%d/%d] delay: %d..." % (attempt, maxattempts, delay))
		try:
			# создаем класс
			t = Touchbank(
				login=cmd_args.login, 
				password=cmd_args.password, 
				delay=delay, 
				logger=logger, 
				debug=True
			)
			# исполняем команду
			if cmd_args.cmd == 'card-balance':
				print t.get_card_balance()['balance']
		
			elif cmd_args.cmd == 'hold-balance':
				print t.get_hold_balance()['balance']
		
			elif cmd_args.cmd == 'transfer':
				if cmd_args.amount and cmd_args.template:
					if cmd_args.amount == 'all-from-card':
						logger.debug("Checking card balance")
						amount = t.get_card_balance()['balance']
					elif cmd_args.amount == 'all-from-hold':
						logger.debug("Checking hold balance")
						amount = t.get_hold_balance()['balance']
					else:
						amount = float(cmd_args.amount)
					if t.transfer(amount=amount, template=cmd_args.template):
						logger.info("Successfull transfer on [%d/%d] attempt" % (attempt, maxattempts))
					else:
						logger.error("Transfer failed")
				else:
					print "Not enough transfer parameters(template name and transfer amount)"
		except Exception, e:
			attempt +=1
			delay +=delay_amp
			logger.debug(str(e))
		else:
			break
			




