import json

from ibm_graph import Edge
from ibm_graph import Vertex
from ibm_graph.schema import EdgeLabel
from ibm_graph.schema import PropertyKey
from ibm_graph.schema import Schema
from ibm_graph.schema import VertexIndex
from ibm_graph.schema import VertexLabel


class GraphRecipeStore(object):

    def __init__(self, graph_client, graph_id):
        """
        Creates a new instance of GraphRecipeStore.
        Parameters
        ----------
        graph_client - The instance of the IBM Graph client to use
        graph_id - The id of the graph to use
        """
        self.graph_client = graph_client
        self.graph_id = graph_id

    def init(self):
        """
        Creates and initializes the Graph and Graph schema.
        """
        print('Getting graphs...')
        graph_ids = self.graph_client.get_graphs()
        graph_exists = (self.graph_id in graph_ids)
        if not graph_exists:
            print('Creating graph {}...'.format(self.graph_id))
            self.graph_client.create_graph(self.graph_id)
        # set graph
        self.graph_client.set_graph(self.graph_id)
        # create schema if not exists
        print('Getting graph schema...')
        schema = self.graph_client.get_schema()
        schema_exists = (schema is not None and schema.property_keys is not None and len(schema.property_keys) > 0)
        if not schema_exists:
            print('Creating graph schema...')
            schema = Schema([
                    PropertyKey('name', 'String', 'SINGLE'),
                    PropertyKey('title', 'String', 'SINGLE'),
                    PropertyKey('detail', 'String', 'SINGLE')
                ],
                [
                    VertexLabel('person'),
                    VertexLabel('ingredient'),
                    VertexLabel('cuisine'),
                    VertexLabel('recipe')
                ],
                [
                    EdgeLabel('selects')
                ],
                [
                    VertexIndex('vertexByName', ['name'], True, True)
                ],
                []
            )
            self.graph_client.save_schema(schema)
        else:
            print('Graph Schema exists.')

    # User

    def add_user(self, user_id):
        """
        Adds a new user to Graph if a user with the specified ID does not already exist.
        Parameters
        ----------
        user_id - The ID of the user (typically the ID returned from Slack)
        """
        vertex = Vertex('person', {
            'name': user_id
        })
        return self.add_vertex_if_not_exists(vertex, 'name')

    # Ingredients

    @staticmethod
    def get_unique_ingredients_name(ingredients_str):
        """
        Gets the unique name for the ingredient to be stored in Graph.
        Parameters
        ----------
        ingredient_str - The ingredient or comma-separated list of ingredients specified by the user
        """
        ingredients = [x.strip() for x in ingredients_str.lower().strip().split(',')]
        ingredients.sort()
        return ','.join([x for x in ingredients])

    def find_ingredient(self, ingredients_str):
        """
        Finds the ingredient based on the specified ingredientsStr in Graph.
        Parameters
        ----------
        ingredient_str - The ingredient or comma-separated list of ingredients specified by the user
        """
        return self.find_vertex('ingredient', 'name', self.get_unique_ingredients_name(ingredients_str))

    def add_ingredient(self, ingredients_str, matching_recipes, user_vertex):
        """
        Adds a new ingredient to Graph if an ingredient based on the specified ingredientsStr does not already exist.
        Parameters
        ----------
        ingredient_str - The ingredient or comma-separated list of ingredients specified by the user
        matching_recipes - The recipes that match the specified ingredientsStr
        user_vertex - The existing Graph vertex for the user
        """
        ingredient_vertex = Vertex('ingredient', {
            'name': self.get_unique_ingredients_name(ingredients_str),
            'detail': json.dumps(matching_recipes)
        })
        ingredient_vertex = self.add_vertex_if_not_exists(ingredient_vertex, 'name')
        self.record_ingredient_request_for_user(ingredient_vertex, user_vertex)
        return ingredient_vertex

    def record_ingredient_request_for_user(self, ingredient_vertex, user_vertex):
        """
        Creates or updates an edge between the specified user and ingredient.
        Stores the number of times the ingredient has been accessed by the user in the edge.
        Parameters
        ----------
        ingredient_vertex - The existing Graph vertex for the ingredient
        user_vertex - The existing Graph vertex for the user
        """
        ingredient_edge = Edge('selects', user_vertex.id, ingredient_vertex.id, {
            'count': 1
        })
        self.add_update_edge(ingredient_edge)

    # Cuisine

    @staticmethod
    def get_unique_cuisine_name(cuisine):
        """
        Gets the unique name for the cuisine to be stored in Graph.
        Parameters
        ----------
        cuisine - The cuisine specified by the user
        """
        return cuisine.strip().lower()

    def find_cuisine(self, cuisine_str):
        """
        Finds the cuisine with the specified name in Graph.
        Parameters
        ----------
        cuisine - The cuisine specified by the user
        """
        return self.find_vertex('cuisine', 'name', self.get_unique_cuisine_name(cuisine_str))

    def add_cuisine(self, cuisine_str, matching_recipes, user_vertex):
        """
        Adds a new cuisine to Graph if a cuisine with the specified name does not already exist.
        Parameters
        ----------
        cuisine - The cuisine specified by the user
        matching_recipes - The recipes that match the specified cuisine
        user_vertex - The existing Graph vertex for the user
        """
        cuisine_vertex = Vertex('cuisine', {
            'name': self.get_unique_cuisine_name(cuisine_str),
            'detail': json.dumps(matching_recipes)
        })
        cuisine_vertex = self.add_vertex_if_not_exists(cuisine_vertex, 'name')
        self.record_cuisine_request_for_user(cuisine_vertex, user_vertex)
        return cuisine_vertex

    def record_cuisine_request_for_user(self, cuisine_vertex, user_vertex):
        """
        Creates or updates an edge between the specified user and cuisine.
        Stores the number of times the cuisine has been accessed by the user in the edge.
        Parameters
        ----------
        cuisine_vertex - The existing Graph vertex for the cuisine
        user_vertex - The existing Graph vertex for the user
        """
        cuisine_edge = Edge('selects', user_vertex.id, cuisine_vertex.id, {
            'count': 1
        })
        self.add_update_edge(cuisine_edge)

    # Recipe

    @staticmethod
    def get_unique_recipe_name(recipe_id):
        """
        Gets the unique name for the recipe to be stored in Graph.
        Parameters
        ----------
        recipe_id - The ID of the recipe (typically the ID of the recipe returned from Spoonacular)
        """
        return str(recipe_id).strip().lower()

    def find_recipe(self, recipe_id):
        """
        Finds the recipe with the specified ID in Graph.
        Parameters
        ----------
        recipe_id - The ID of the recipe (typically the ID of the recipe returned from Spoonacular)
        """
        return self.find_vertex('recipe', 'name', self.get_unique_recipe_name(recipe_id))

    def add_recipe(self, recipe_id, recipe_title, recipe_detail, ingredient_cuisine_vertex, user_vertex):
        """
        Adds a new recipe to Graph if a recipe with the specified name does not already exist.
        Parameters
        ----------
        recipe_id - The ID of the recipe (typically the ID of the recipe returned from Spoonacular)
        recipe_title - The title of the recipe
        recipe_detail - The detailed instructions for making the recipe
        ingredient_cuisine_vertex - The existing Graph vertex for either the ingredient or cuisine selected before the recipe
        user_vertex - The existing Graph vertex for the user
        """
        recipe_vertex = Vertex('recipe', {
            'name': self.get_unique_recipe_name(recipe_id),
            'title': recipe_title.strip(),
            'detail': recipe_detail
        })
        recipe_vertex = self.add_vertex_if_not_exists(recipe_vertex, 'name')
        self.record_recipe_request_for_user(recipe_vertex, ingredient_cuisine_vertex, user_vertex)
        return recipe_vertex

    def find_favorite_recipes_for_user(self, user_vertex, count):
        """
        Finds the user's favorite recipes in Graph.
        Parameters
        ----------
        user_vertex - The existing Graph vertex for the user
        count - The max number of recipes to return
        """
        query = 'g.V().hasLabel("person").has("name", "{}").outE().order().by("count", decr).inV().hasLabel("recipe").limit({})'.format(user_vertex.get_property_value('name'), count)
        recipe_vertices = self.graph_client.run_gremlin_query(query)
        if len(recipe_vertices) > 0:
            recipes = []
            for recipe_vertex in recipe_vertices:
                recipes.append({
                    'id': recipe_vertex.get_property_value('name'),
                    'title': recipe_vertex.get_property_value('title')
                })
            return recipes
        else:
            return []

    def find_recommended_recipes_for_ingredient(self, ingredients_str, user_vertex, count):
        """
        Finds popular recipes using the specified ingredient.
        Parameters
        ----------
        ingredients_str - The ingredient or comma-separated list of ingredients specified by the user
        user_vertex - The Graph vertex for the user requesting recommended recipes
        count - The max number of recipes to return
        """
        ingredients_str = self.get_unique_ingredients_name(ingredients_str)
        query = 'g.V().hasLabel("ingredient").has("name","{}")'.format(ingredients_str)
        query += '.in("has")'
        query += '.inE().has("count",gt(1)).order().by("count", decr)'
        query += '.outV().hasLabel("person").has("name",neq("{}"))'.format(user_vertex.get_property_value('name'))
        query += '.path()'
        return self.get_recommended_recipes(query, count)

    def find_recommended_recipes_for_cuisine(self, cuisine, user_vertex, count):
        """
        Finds popular recipes using the specified cuisine.
        Parameters
        ----------
        cuisine - The cuisine specified by the user
        user_vertex - The Graph vertex for the user requesting recommended recipes
        count - The max number of recipes to return
        """
        cuisine = self.get_unique_cuisine_name(cuisine)
        query = 'g.V().hasLabel("cuisine").has("name","{}")'.format(cuisine)
        query += '.in("has")'
        query += '.inE().has("count",gt(1)).order().by("count", decr)'
        query += '.outV().hasLabel("person").has("name",neq("{}"))'.format(user_vertex.get_property_value('name'))
        query += '.path()'
        return self.get_recommended_recipes(query, count)

    def get_recommended_recipes(self, query, count):
        paths = self.graph_client.run_gremlin_query(query)
        if len(paths) > 0:
            recipes = []
            for path in paths:
                recipe_vertex = path.objects[1]
                recipe_id = recipe_vertex.get_property_value('name')
                existing_recipes = list(filter(lambda x: x['id'] == recipe_id, recipes))
                if len(existing_recipes) == 0:
                    if len(recipes) >= count:
                        continue
                    else:
                        recipes.append({
                            'id': recipe_id,
                            'title': recipe_vertex.get_property_value('title'),
                            'recommendedUserCount': 1
                        })
                else:
                    existing_recipes[0]['recommendedUserCount'] += 1
            return recipes
        else:
            return []

    def record_recipe_request_for_user(self, recipe_vertex, ingredient_cuisine_vertex, user_vertex):
        """
        Creates or updates an edge between the specified user and recipe.
        Stores the number of times the recipe has been accessed by the user in the edge.
        Creates or updates an edge between the specified ingredient/cuisine (if not None) and recipe.
        Stores the number of times the recipe has been accessed by the ingredient/cuisine in the edge.
        Parameters
        ----------
        recipe_vertex - The existing Graph vertex for the recipe
        ingredient_cuisine_vertex - The existing Graph vertex for either the ingredient or cuisine selected before the recipe
        user_vertex - The existing Graph vertex for the user
        """
        # add one edge from the user to the recipe (this will let us find a user's favorite recipes, etc)
        edge = Edge('selects', user_vertex.id, recipe_vertex.id, {
            'count': 1
        })
        self.add_update_edge(edge)
        if ingredient_cuisine_vertex is not None:
            # add "selects" edge from ingredient/cuisine to recipe
            edge = Edge('selects', ingredient_cuisine_vertex.id, recipe_vertex.id, {
                'count': 1
            })
            self.add_update_edge(edge)
            # add "has" edge from recipe to ingredient/cuisine
            edge = Edge('has', recipe_vertex.id, ingredient_cuisine_vertex.id)
            self.add_edge_if_not_exists(edge)

    # Graph Helper Methods

    def find_vertex(self, label, property_name, property_value):
        """
        Finds a vertex based on the specified label, property_name, and property_value.
        Parameters
        ----------
        label - The label value of the vertex stored in Graph
        property_name - The property name to search for
        property_value - The value that should match for the specified property name
        """
        query = 'g.V().hasLabel("{}").has("{}", "{}")'.format(label, property_name, property_value)
        response = self.graph_client.run_gremlin_query(query)
        if len(response) > 0:
            return response[0]
        else:
            return None

    def add_vertex_if_not_exists(self, vertex, unique_property_name):
        """
        Adds a new vertex to Graph if a vertex with the same value for unique_property_name does not exist.
        Parameters
        ----------
        vertex - The vertex to add
        unique_property_name - The name of the property used to search for an existing vertex (the value will be extracted from the vertex provided)
        """
        property_value = vertex.get_property_value(unique_property_name)
        query = 'g.V().hasLabel("{}").has("{}", "{}")'.format(vertex.label, unique_property_name, property_value)
        response = self.graph_client.run_gremlin_query(query)
        if len(response) > 0:
            print('Returning {} vertex where {}={}'.format(vertex.label, unique_property_name, property_value))
            return response[0]
        else:
            print('Creating {} vertex where {}={}'.format(vertex.label, unique_property_name, property_value))
            return self.graph_client.add_vertex(vertex)

    def add_edge_if_not_exists(self, edge):
        """
        Adds a new edge to Graph if an edge with the same out_v and in_v does not exist.
        Parameters
        ----------
        edge - The edge to add
        """
        query = 'g.V({}).outE().inV().hasId({}).path()'.format(edge.out_v, edge.in_v)
        response = self.graph_client.run_gremlin_query(query)
        if len(response) > 0:
            print('Edge from {} to {} exists.'.format(edge.out_v, edge.in_v))
        else:
            print('Creating edge from {} to {}'.format(edge.out_v, edge.in_v))
            self.graph_client.add_edge(edge)

    def add_update_edge(self, edge):
        """
        Adds a new edge to Graph if an edge with the same out_v and in_v does not exist.
        Increments the count property on the edge.
        Parameters
        ----------
        edge - The edge to add
        """
        query = 'g.V({}).outE().inV().hasId({}).path()'.format(edge.out_v, edge.in_v)
        response = self.graph_client.run_gremlin_query(query)
        if len(response) > 0:
            print('Edge from {} to {} exists.'.format(edge.out_v, edge.in_v))
            edge = response[0].objects[1]
            edge_count = edge.get_property_value('count')
            count = 0
            if edge_count is not None:
                count += edge_count
            edge.set_property_value('count', count+1)
            self.graph_client.update_edge(edge)
        else:
            print('Creating edge from {} to {}'.format(edge.out_v, edge.in_v))
            self.graph_client.add_edge(edge)
