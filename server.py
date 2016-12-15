import deployment_tracker
import os

from dotenv import load_dotenv
from ibm_graph import IBMGraphClient
from slackclient import SlackClient
from watson_developer_cloud import ConversationV1

from souschef.graph_recipe_store import GraphRecipeStore
from souschef.recipe import RecipeClient
from souschef.sns_client import SNSClient
from souschef.souschef import SousChef

try:
    from SimpleHTTPServer import SimpleHTTPRequestHandler as Handler
    from SocketServer import TCPServer as Server
except ImportError:
    from http.server import SimpleHTTPRequestHandler as Handler
    from http.server import HTTPServer as Server

# Read port selected by the cloud for our application
PORT = int(os.getenv('PORT', 8000))
# Change current directory to avoid exposure of control files
os.chdir('static')

httpd = Server(("", PORT), Handler)
try:
    # track deployment
    deployment_tracker.track()
    # load environment variables
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    slack_bot_id = os.environ.get("SLACK_BOT_ID")
    slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
    conversation_workspace_id = os.environ.get("CONVERSATION_WORKSPACE_ID")
    conversation_client = ConversationV1(
        username=os.environ.get("CONVERSATION_USERNAME"),
        password=os.environ.get("CONVERSATION_PASSWORD"),
        version='2016-07-11'
    )
    recipe_client = RecipeClient(os.environ.get("SPOONACULAR_KEY"))
    recipe_store = GraphRecipeStore(
        IBMGraphClient(
            os.environ.get("GRAPH_API_URL"),
            os.environ.get("GRAPH_USERNAME"),
            os.environ.get("GRAPH_PASSWORD")
        ),
        os.environ.get("GRAPH_ID")
    )
    sns_client = SNSClient(
        os.environ.get("SNS_API_URL"),
        os.environ.get("SNS_API_KEY")
    )
    # start the souschef bot
    souschef = SousChef(slack_bot_id,
                        slack_client,
                        conversation_client,
                        conversation_workspace_id,
                        recipe_client,
                        recipe_store,
                        sns_client)
    souschef.start()
    # start the http server
    print("Start serving at port %i" % PORT)
    httpd.serve_forever()
except (KeyboardInterrupt, SystemExit):
    pass
souschef.stop()
souschef.join()
httpd.server_close()
