import requests as r
import json
import time
import random


__all__ = ['cast_vote']

GOOD_HEADERS = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}



def parse(text, start, end = None): #simple utility for parsing strings
    newtext = text[text.find(start)+len(start):]
    if end != None:
        newtext = newtext[:newtext.find(end)]
    return newtext



class vote: #class that represents a vote on pollEV
    
    def __init__(self, poll):
        self.ses = r.session() #the session that the voter does everything in
        self.good_headers = GOOD_HEADERS.copy() #can't use the global headers because I'm gonna change them when I have an auth token
        self.poll = poll
        self.id = None
        self.data = None
        self.csrf_token = None
        self.vote_cast_response = None

    def get(self, url):
        return self.ses.get(url, headers = GOOD_HEADERS, timeout = 20)

    def gen_user_id(self):
        return ''.join(str(int(random.random()*10)) for i in range(13)) #just 13 random digits, pretty ghetto
        #return str(int(time.time()*1000))  #this is how the site itself generates user ids which is even worse tbh

    def get_vote_data(self):
        return self.get('https://pollev.com/proxy/api/profile?_=' + self.id)
    
    def login_to_poll(self, poll_master):
        self.id = self.gen_user_id()
        self.data = self.get_vote_data()
        self.csrf_token = self.data.headers['X-CSRF-Token'] #lets me auth my vote
        self.poll.get_id(self)
        self.poll.get_data(self)

    def cast_vote(self, choice):
        self.good_headers['x-csrf-token'] = self.csrf_token
        if self.poll.type == 'multi':
            result = self.cast_multi_vote(choice)
        elif self.poll.type == 'text':
            result = self.cast_text_vote(choice)
        else:
            raise Exception("Can't cast vote before logging into a text or multiple choice poll")
        if not self.check_vote_response(result): #if there was an auth problem
            self.ses = r.session() #reset the session
            return self.vote(choice) #re vote
        return result
        
    
    def cast_multi_vote(self, choice):
        if type(choice) != int or choice < 0:
            raise Exception('Multiple choice polls must have an integer >= 0 as the choice')
        try:
            choice_info = self.poll.options[choice]
        except IndexError:
            raise Exception(str(choice) + ' is not a valid choice on this poll. The choices on this poll only range from 0 to '
                            + str(len(self.poll.options) - 1))
        choice_id = str(choice_info['id'])
        choice_value = choice_info['value']
        result = self.ses.post('https://pollev.com/proxy/multiple_choice_polls/' #Example post url: post_url = 'https://pollev.com/proxy/multiple_choice_polls/xpv75WMERh6UyNl/options/122196203/results.json?include_confirmation_message=1'
                      + self.poll.id
                      +'/options/'
                      + choice_id
                      +'/results.json?include_confirmation_message=1', #example post data: post_json = {"result":{"value":"C","accumulator_id":122196202,"poll_id":37080031,"source":"pollev_page"}}
                      json = {"result":
                              {"value": choice_value,
                               "accumulator_id": choice_id,
                               "poll_id": self.poll.int_id,
                               "source":"pollev_page"
                               }},
                      headers = self.good_headers
                      )
        self.vote_cast_response = result
        return result

    def cast_text_vote(self, choice):
        choice = unicode(choice)
        result = self.ses.post('https://pollev.com/proxy/free_text_polls/'
                      + self.poll.id
                      +'/results.json?include_confirmation_message=1',
                      json = {"result":
                              {"value": choice,
                               "humanized_value": choice,
                               "poll_id": self.poll.int_id,
                               "source":"pollev_page"
                               }},
                      headers = self.good_headers
                      )
        self.vote_cast_response = result
        return result

    def check_vote_response(self, result):
        if result.status_code != 200:
            error = result.content
            if "Invalid authenticity token" in error: #if its an auth token problem
                print "[PollEV info] Invalid authenticity token, recasting vote"
                return False
            elif "You can't respond to this poll any more." in error:
                raise Exception("Vote wasn't cast, likely because you're voting too quickly (try putting a time.sleep(0.01) between every vote)\nActual error was: "
                                + error)
            else: #if there was a different kind of problem
                raise Exception("Vote was not cast! Vote cast returned status "
                                + str(result.status_code)
                                + " because: "
                                + error)
        return True

    def vote(self, choice):
        self.login_to_poll(self.poll.master)
        self.cast_vote(choice)
        return self.vote_cast_response



class poll: #class that represents a poll on pollEV
    
    def __init__(self, poll_master):
        self.master = poll_master
        self.id = None
        self.data = None
        self.options = None
        self.int_id = None
        self.type = None

    def get_id(self, voter):
        for loop_num in range(1, 4): #loops so it can retry if it gets a bad gateway
            poll_basic_info = voter.get('https://firehose-production.polleverywhere.com/users/'
                                   + self.master
                                   + '/activity/current.json?last_message_sequence=0&_='
                                   + voter.id
                                ).content
            self.id = parse(poll_basic_info, '"uid\\":\\"', '\\"')
            if len(self.id) < 10 or len(self.id) > 20: #check if theres a 502 response or some other error
                if '<head><title>502 Bad Gateway</title></head>' in poll_basic_info: #if we get a 502 we can usually just retry the vote and it should work
                    print "[PollEV info] 502 when getting poll info, trying to get poll info agian... (" + str(loop_num) + "/3)" 
                else: #if there was a bad error
                    raise Exception("Poll info wasn't recieved properly, server returned: " + poll_basic_info)
            else: #if theres no errors, just return the id
                return self.id
        raise Exception("Got repeating 502 responses when retrieving poll info")

    def get_data(self, voter):
        poll_info = voter.get('https://pollev.com/proxy/api/polls/'
                                 + self.id
                                 +'?_='
                                 + voter.id)
        self.data = json.loads(poll_info.content)
        self.extract_info_from_data(self.data)
        return self.data

    def extract_info_from_data(self, data):
        if 'multiple_choice_poll' in data:
            self.type = 'multi'
            self.options = data['multiple_choice_poll']['options']
            self.int_id = data['multiple_choice_poll']['id']
        elif 'free_text_poll' in data:
            self.type = 'text'
            self.int_id = data['free_text_poll']['id']
        else:
            raise Exception('Invalid poll type (not multiple choice or free text)')


def cast_vote(poll_master, choice):
    return vote(poll(poll_master)).vote(choice)
