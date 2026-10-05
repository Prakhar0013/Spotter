"""Built-in nutrition table.

Values are approximate, per 100 g (or 100 ml for drinks), based on USDA
FoodData Central and the Indian Food Composition Tables. `units` maps a
household unit to grams. Anything missing here can be estimated by the local
model once and then saved as a custom food you can correct.
"""


def f(kcal, protein, carbs, fat, units=None, aliases=()):
    return {"kcal": kcal, "protein": protein, "carbs": carbs, "fat": fat,
            "units": units or {}, "aliases": list(aliases)}


FOODS = {
    # Protein
    "egg": f(155, 13, 1.1, 11, {"piece": 50}, ["eggs", "boiled egg", "whole egg", "omelette", "omelet"]),
    "egg white": f(52, 11, 0.7, 0.2, {"piece": 33}, ["egg whites"]),
    "chicken breast": f(165, 31, 0, 3.6, {"piece": 150, "serving": 150}, ["grilled chicken", "chicken"]),
    "chicken curry": f(150, 14, 4, 9, {"bowl": 200, "serving": 200}),
    "mutton curry": f(200, 16, 3, 14, {"bowl": 200, "serving": 200}),
    "fish": f(128, 22, 0, 4, {"piece": 120, "serving": 150}, ["fish fillet", "rohu"]),
    "salmon": f(206, 22, 0, 12, {"piece": 150}),
    "tuna": f(116, 26, 0, 1, {"can": 120}, ["canned tuna"]),
    "paneer": f(265, 18, 1.2, 21, {"serving": 100, "piece": 25}, ["cottage cheese"]),
    "tofu": f(76, 8, 1.9, 4.8, {"serving": 100}),
    "soya chunks": f(345, 52, 33, 0.5, {"cup": 50, "serving": 50}, ["soy chunks", "nutrela"]),
    "whey protein": f(400, 80, 8, 6, {"scoop": 30}, ["whey", "protein shake", "protein powder"]),
    "protein bar": f(360, 30, 40, 10, {"piece": 60}),
    # Dairy
    "milk": f(60, 3.2, 4.8, 3.0, {"glass": 250, "cup": 240}, ["toned milk"]),
    "curd": f(61, 3.5, 4.7, 3.3, {"bowl": 150, "cup": 245}, ["dahi", "yogurt", "yoghurt"]),
    "greek yogurt": f(59, 10, 3.6, 0.4, {"cup": 170, "bowl": 170}),
    "buttermilk": f(25, 1.5, 2.5, 1, {"glass": 250}, ["chaas"]),
    "cheese slice": f(300, 18, 6, 23, {"slice": 20, "piece": 20}, ["cheese"]),
    "butter": f(717, 0.9, 0.1, 81, {"tbsp": 14, "tsp": 5}),
    "ghee": f(900, 0, 0, 100, {"tbsp": 13, "tsp": 5}),
    # Carbs and staples
    "white rice": f(130, 2.7, 28, 0.3, {"cup": 160, "bowl": 200, "plate": 250}, ["rice", "cooked rice", "chawal"]),
    "brown rice": f(112, 2.3, 24, 0.8, {"cup": 160, "bowl": 200}),
    "roti": f(297, 9.6, 46, 7.4, {"piece": 40}, ["chapati", "phulka", "chapatti"]),
    "paratha": f(326, 6.4, 45, 13, {"piece": 80}, ["aloo paratha"]),
    "oats": f(389, 16.9, 66, 6.9, {"cup": 80, "tbsp": 10, "bowl": 50}, ["oatmeal", "rolled oats"]),
    "white bread": f(265, 9, 49, 3.2, {"slice": 25}, ["bread"]),
    "brown bread": f(247, 13, 41, 3.4, {"slice": 28}, ["whole wheat bread", "multigrain bread"]),
    "pasta": f(158, 5.8, 31, 0.9, {"cup": 140, "bowl": 200, "plate": 250}),
    "potato": f(87, 1.9, 20, 0.1, {"piece": 150}, ["boiled potato", "aloo"]),
    "sweet potato": f(76, 1.4, 17.7, 0.1, {"piece": 150}),
    "poha": f(180, 3.5, 30, 5, {"plate": 200, "bowl": 150}),
    "upma": f(150, 3.5, 22, 5, {"plate": 200, "bowl": 150}),
    "idli": f(146, 4.5, 30, 0.4, {"piece": 40}),
    "dosa": f(168, 3.9, 29, 3.7, {"piece": 75}),
    "khichdi": f(120, 4.5, 20, 2.5, {"bowl": 250, "plate": 300}),
    "instant noodles": f(440, 9, 62, 17, {"pack": 70}, ["maggi"]),
    # Legumes and curries
    "dal": f(105, 6.5, 15, 2.5, {"bowl": 200, "cup": 200}, ["dal tadka", "lentils", "dal fry"]),
    "rajma": f(127, 8.7, 22.8, 0.5, {"bowl": 200}, ["kidney beans"]),
    "chole": f(164, 8.9, 27.4, 2.6, {"bowl": 200}, ["chickpeas", "chana"]),
    "sambar": f(60, 3, 9, 1.5, {"bowl": 200}),
    "mixed veg sabzi": f(90, 2.5, 9, 5, {"bowl": 150}, ["sabzi", "vegetable curry", "veg curry"]),
    # Vegetables and fruit
    "broccoli": f(34, 2.8, 7, 0.4, {"cup": 90}),
    "spinach": f(23, 2.9, 3.6, 0.4, {"cup": 30}, ["palak"]),
    "salad": f(20, 1, 4, 0.2, {"bowl": 150, "plate": 150}, ["green salad", "mixed salad"]),
    "banana": f(89, 1.1, 22.8, 0.3, {"piece": 118}),
    "apple": f(52, 0.3, 14, 0.2, {"piece": 180}),
    "orange": f(47, 0.9, 12, 0.1, {"piece": 130}),
    "mango": f(60, 0.8, 15, 0.4, {"piece": 200}),
    "watermelon": f(30, 0.6, 7.6, 0.2, {"cup": 150, "bowl": 250}),
    # Fats, nuts, extras
    "peanut butter": f(588, 25, 20, 50, {"tbsp": 16, "tsp": 5}),
    "peanuts": f(567, 25.8, 16, 49, {"handful": 30}),
    "almonds": f(579, 21, 22, 50, {"piece": 1.2, "handful": 28}, ["badam"]),
    "olive oil": f(884, 0, 0, 100, {"tbsp": 13.5, "tsp": 4.5}, ["oil", "cooking oil"]),
    "honey": f(304, 0.3, 82, 0, {"tbsp": 21, "tsp": 7}),
    "sugar": f(387, 0, 100, 0, {"tsp": 4, "tbsp": 12.5}),
    # Drinks and outside food
    "tea with milk": f(40, 1, 6.5, 1, {"cup": 150}, ["chai", "tea"]),
    "black coffee": f(2, 0.3, 0, 0, {"cup": 240}, ["coffee", "americano"]),
    "cola": f(42, 0, 10.6, 0, {"can": 330, "glass": 250}, ["coke", "pepsi", "soft drink"]),
    "pizza": f(266, 11, 33, 10, {"slice": 107}),
    "burger": f(250, 13, 28, 10, {"piece": 220}),
    "samosa": f(308, 5, 32, 18, {"piece": 60}),
}
