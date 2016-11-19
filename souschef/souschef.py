import json
import os
import pprint
import time
from slackclient import SlackClient
from recipe import RecipeClient
from user_state import UserState


class SousChef:
    def __init__(self, recipe_graph, bot_id, slack_client, conversation_client, conversation_workspace_id,
                 recipe_client):
        self.recipe_graph = recipe_graph
        self.bot_id = bot_id

        self.slack_client = slack_client
        self.conversation_client = conversation_client
        self.recipe_client = recipe_client

        self.at_bot = "<@" + bot_id + ">:"
        self.delay = 0.5  # second
        self.workspace_id = conversation_workspace_id

        self.user_state_map = {}

        self.pp = pprint.PrettyPrinter(indent=4)

    def parse_slack_output(self, slack_rtm_output):
        output_list = slack_rtm_output
        if output_list and len(output_list) > 0:
            for output in output_list:
                print json.dumps(output)
                if output and 'text' in output and 'user_profile' not in output and self.at_bot in output['text']:
                    return output['text'].split(self.at_bot)[1].strip().lower(), output['user'], output['channel']
                elif output and 'text' in output and 'user_profile' not in output:
                    return output['text'].lower(), output['user'], output['channel']
        return None, None, None

    def post_to_slack(self, response, channel):
        self.slack_client.api_call("chat.postMessage",
                                   channel=channel,
                                   text=response, as_user=True)

    def make_formatted_steps(self, recipe_info, recipe_steps):
        response = "Ok, it takes *" + \
                   str(recipe_info['readyInMinutes']) + \
                   "* minutes to make *" + \
                   str(recipe_info['servings']) + \
                   "* servings of *" + \
                   recipe_info['title'] + "*. Here are the steps:\n\n"

        if recipe_steps and recipe_steps[0]['steps']:
            for i, r_step in enumerate(recipe_steps[0]['steps']):
                equip_str = ""
                for e in r_step['equipment']:
                    equip_str += e['name'] + ", "
                if not equip_str:
                    equip_str = "None"
                else:
                    equip_str = equip_str[:-2]

                response += "*Step " + str(i + 1) + "*:\n" + \
                            "_Equipment_: " + equip_str + "\n" + \
                            "_Action_: " + r_step['step'] + "\n\n"
        else:
            response += "_No instructions available for this recipe._\n\n"

        response += "*Say anything to me to start over...*"
        return response

    def handle_start_message(self, state, watson_response):
        if state.user_vertex is None:
            user_vertex = self.recipe_graph.add_user_vertex(state.user_id)
            state.user_vertex = user_vertex
        response = ''
        for text in watson_response['output']['text']:
            response += text + "\n"
        return response

    def handle_ingredients_message(self, state, message):
        if state.conversation_context['get_recipes']:
            state.conversation_context['recipes'] = \
                self.recipe_client.find_by_ingredients(message)

        response = "Lets see here...\n" + \
                   "I've found these recipes: \n"

        for i, recipe in enumerate(state.conversation_context['recipes']):
            response += str(i + 1) + ". " + recipe['title'] + "\n"
        response += "\nPlease enter the corresponding number of your choice."

        return response

    def handle_cuisine_message(self, state, cuisine):
        if state.conversation_context['get_recipes']:
            state.conversation_context['recipes'] = self.recipe_client.find_by_cuisine(cuisine)

        response = "Lets see here...\n" + \
                   "I've found these recipes: \n"

        for i, recipe in enumerate(state.conversation_context['recipes']):
            response += str(i + 1) + ". " + recipe['title'] + "\n"
        response += "\nPlease enter the corresponding number of your choice."

        return response

    def handle_selection_message(self, state, selection):
        recipe_id = state.conversation_context['recipes'][selection - 1]['id']
        recipe_info = self.recipe_client.get_info_by_id(recipe_id)
        recipe_steps = self.recipe_client.get_steps_by_id(recipe_id)

        return self.make_formatted_steps(recipe_info, recipe_steps)

    def handle_message(self, message, message_sender, channel):

        # get or create state for the user
        if message_sender in self.user_state_map.keys():
            state = self.user_state_map[message_sender]
        else:
            state = UserState(message_sender)
            self.user_state_map[message_sender] = state

        watson_response = self.conversation_client.message(
            workspace_id=self.workspace_id,
            message_input={'text': message},
            context=state.conversation_context)

        # print json.dumps(watson_response)

        state.conversation_context = watson_response['context']

        if 'is_favorites' in state.conversation_context.keys() and state.conversation_context['is_favorites']:
            response = self.handle_favorites_message(state)

        elif 'is_ingredients' in state.conversation_context.keys() and state.conversation_context['is_ingredients']:
            response = self.handle_ingredients_message(state, message)

        elif 'is_selection' in state.conversation_context.keys() and state.conversation_context['is_selection']:
            state.conversation_context['selection_valid'] = False
            response = "Invalid selection! " + \
                       "Say anything to see your choices again..."

            if state.conversation_context['selection'].isdigit():
                selection = int(state.conversation_context['selection'])
                if selection >= 1 and selection <= 5:
                    state.conversation_context['selection_valid'] = True
                    response = self.handle_selection_message(state, selection)

        elif watson_response['entities'] and \
                        watson_response['entities'][0]['entity'] == 'cuisine':
            cuisine = watson_response['entities'][0]['value']
            response = self.handle_cuisine_message(state, cuisine)

        else:
            response = self.handle_start_message(state, watson_response)

        self.post_to_slack(response, channel)

    def run(self):
        self.recipe_graph.init_graph()
        if self.slack_client.rtm_connect():
            print("sous-chef is connected and running!")
            while True:
                slack_output = self.slack_client.rtm_read()
                message, message_sender, channel = self.parse_slack_output(slack_output)
                if message and channel:
                    self.handle_message(message, message_sender, channel)
                time.sleep(self.delay)
        else:
            print("Connection failed. Invalid Slack token or bot ID?")
