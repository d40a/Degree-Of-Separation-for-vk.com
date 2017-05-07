
from __future__ import unicode_literals
from django.http import HttpResponse
from django.shortcuts import render

import vk
import requests
import time
import json

ACCESS_TOKEN = 'e8e77b6ed30fb2f8d38ea2ed74d0842b677c990c0fa15551fc9317adad20eb6a52e046bb0714e15a25216'
REDIRECT_URI = 'http://198.211.121.159/dos/'
CLIENT_ID = '6011990'
VERSION = '5.63'

REQUESTS_CNT_PER_EXEC_METHOD = 25
REQUESTS_PER_SEC = 3
MAX_DEPTH_OF_TREE = 3
FRIENDS_AMOUNT_THRESHOLD = 250


def login(request):

	auth_url = "https://oauth.vk.com/authorize?client_id={0}&display=page&redirect_uri={1}&scope=friends&response_type=code&v={2}"
	auth_url = auth_url.format(CLIENT_ID, REDIRECT_URI, VERSION)

	if not request.GET.get('code'):
		return render(request, 'dos/login.html', {
			'data': {
				'auth_url': auth_url
			}
		})
	else:
		access_token_url = 'https://oauth.vk.com/access_token?client_id=6011990&client_secret=NOOAEMoCLSu85EdxMSK8&code={0}&redirect_uri={1}'
		access_token_url = access_token_url.format(request.GET.get('code'), REDIRECT_URI)
		r = requests.get(access_token_url)
		response = r.json()
		global ACCESS_TOKEN
		ACCESS_TOKEN = response['access_token']
		print ACCESS_TOKEN
		return render(request, 'dos/main.html')


def parse_user_login(link):
	prefix = 'https://vk.com/'
	if not link.startswith(prefix):
		raise Exception('Wrong link provided.')
	return link[len(prefix):]

def find_path(request):
	user_login_1 = parse_user_login(request.GET.get('first_user'))
	user_login_2 = parse_user_login(request.GET.get('second_user'))

	session = vk.Session(access_token=ACCESS_TOKEN)
	api = vk.API(session)
	dos = DegreeOfSeparationController(api=api)

	user1 = api.users.get(user_ids=user_login_1)
	user2 = api.users.get(user_ids=user_login_2)
	time.sleep(1.1)
	print user1
	print user2

	path = dos.build_path(user1[0]['uid'], user2[0]['uid'])

	print path
	# TODO: Consider empty path case.
	time.sleep(1.1)
	result = []
	request_cnt = 3
	for id in path:
		result.extend(vk.API(session).users.get(
			user_id=id, 
			fields=['photo_50'],
		))
		request_cnt -= 1
		if request_cnt == 0:
			time.sleep(1.1)
			request_cnt = REQUESTS_PER_SEC

	print result
	return HttpResponse(json.dumps(result))


class DegreeOfSeparationController:
	
	def __init__(self, api):
		self.api = api

	def go_to_next_layer(self, curr_layer, reached, reached_other):
		next_layer = []
		i = 0
		while i < len(curr_layer):

			# Generate codes-scripts to fetch friends of specified users.
			codes = []
			for _ in range(REQUESTS_PER_SEC):
				if i >= len(curr_layer): break
				codes.append(self.gen_friends_request_code(curr_layer[i:i + REQUESTS_CNT_PER_EXEC_METHOD]))
				i += REQUESTS_CNT_PER_EXEC_METHOD

			# For each code build and send get request.
			for code in codes:
				# Send request
				response = self.api.execute(code=code)
				# Process response 
				for item in response:
					if type(item['friends']) is list:
						for j, id in enumerate(item['friends']):
							# Consider first CONST_NUMBER friends for each user. Successive users are skipped.
							# TODO: Do not like it
							if j == FRIENDS_AMOUNT_THRESHOLD: break
							j += 1
							if id not in reached:
								next_layer.append(id)
								reached[id] = item['id']
								if id in reached_other:
									return id

			# Sleep for 1 sec (3 requests per sec)
			print("%s/%s of current layer" % (i, len(curr_layer)))
			time.sleep(1.11)

		curr_layer[:] = next_layer
		return None

	def build_path(self, id1, id2):
		left_layer = [id1]
		right_layer = [id2]

		# for each reached node store it's ancestor
		left_reached = {id1: -1}
		right_reached = {id2: -1}

		for _ in range(MAX_DEPTH_OF_TREE):
			intersection = self.go_to_next_layer(left_layer, left_reached, right_reached)
			if intersection is not None:
				return self.restore_path(intersection, left_reached, right_reached)
			intersection = self.go_to_next_layer(right_layer, right_reached, left_reached)
			if intersection is not None:
				return self.restore_path(intersection, left_reached, right_reached)
		return None

	def restore_path_(self, intersection, reached):
		path = []
		curr = intersection
		while curr != -1:
			path.append(curr)
			curr = reached[curr]
		return path

	def restore_path(self, intersection, left_reached, right_reached):
		print("Intersection in %s" % intersection)
		# left path returned in reverse order
		left_path = self.restore_path_(intersection, left_reached)
		right_path = self.restore_path_(intersection, right_reached)
		# reverse left_path and skip first element because it already exists in
		# right_path
		return left_path[len(left_path) - 1: 0: -1] + right_path

	def gen_friends_request_code(self, user_ids):
		if len(user_ids) > REQUESTS_CNT_PER_EXEC_METHOD:
			raise Exception("To many ids per one execute.")

		code = 'return ['
		for uid in user_ids:
			command = '{ "id" : %s, "friends" : API.friends.get({"user_id" : %s})},' % (uid, uid)
			code += command
		code += '];'
		return code
