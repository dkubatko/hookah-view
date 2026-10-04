"""English labels for HTR's Russian vocabulary (flavor tags, strength, status).

Hand-translated: these are a small closed set and machine translation gets
several of them wrong (e.g. "Холодок" is the cooling agent, not "chill").
Unknown values fall back to the original text.
"""
from __future__ import annotations

STRENGTH = {
    "Лёгкая": ("Light", 1),
    "Средне-лёгкая": ("Medium-light", 2),
    "Средняя": ("Medium", 3),
    "Средне-крепкая": ("Medium-strong", 4),
    "Крепкая": ("Strong", 5),
}

STATUS = {
    "Выпускается": "In production",
    "Снят с производства": "Discontinued",
    "Лимитированный": "Limited",
    "Не известен": "Unknown",
}

COUNTRY = {
    "Россия": "Russia", "США": "USA", "Турция": "Turkey", "ОАЭ": "UAE",
    "Индия": "India", "Египет": "Egypt", "Германия": "Germany", "Иордания": "Jordan",
    "Беларусь": "Belarus", "Казахстан": "Kazakhstan", "Украина": "Ukraine",
}

# group -> (English label, colour); colours follow HTR's own palette.
GROUPS = {
    "Фруктовый": ("Fruity", "#ff6e6e"),
    "Ягодный": ("Berry", "#7b8cf0"),
    "Цитрусовый": ("Citrus", "#ffbe3b"),
    "Десертный": ("Dessert", "#d19a86"),
    "Освежающий": ("Fresh & minty", "#88b3e6"),
    "Специи": ("Spicy", "#e8505c"),
    "Холодные напитки": ("Soft drinks", "#afd2ff"),
    "Алкогольный": ("Cocktails & spirits", "#cfcfcf"),
    "Табачный": ("Tobacco & cigar", "#c0705e"),
    "Сливочный": ("Creamy", "#efc89c"),
    "Горячие напитки": ("Tea & coffee", "#ff7086"),
    "Травяной": ("Herbal", "#3fae7c"),
    "Цветочный": ("Floral", "#ffbedc"),
    "Ореховый": ("Nutty", "#f4d7c9"),
    "Овощной": ("Vegetable", "#7fe64a"),
    "Гастрономический": ("Savoury", "#a48be0"),
    "Хвойный": ("Pine", "#86c43a"),
    "Прочее": ("Other", "#6f9cf0"),
}

TAGS = {
    # citrus
    "Апельсин": "Orange", "Бергамот": "Bergamot", "Грейпфрут": "Grapefruit", "Лайм": "Lime",
    "Лимон": "Lemon", "Мандарин": "Tangerine", "Помело": "Pomelo", "Цитрус": "Citrus",
    # fruit
    "Абрикос": "Apricot", "Айва": "Quince", "Ананас": "Pineapple", "Арбуз": "Watermelon",
    "Банан": "Banana", "Гранат": "Pomegranate", "Груша": "Pear", "Гуава": "Guava",
    "Гуанабана": "Soursop", "Двойное яблоко": "Double apple", "Джекфрут": "Jackfruit",
    "Дыня": "Melon", "Инжир": "Fig", "Карамбола": "Star fruit", "Кивано": "Kiwano",
    "Киви": "Kiwi", "Кокос": "Coconut", "Кумкват": "Kumquat", "Личи": "Lychee",
    "Манго": "Mango", "Мангостин": "Mangosteen", "Маракуйя": "Passion fruit",
    "Марула": "Marula", "Нектарин": "Nectarine", "Папайя": "Papaya", "Персик": "Peach",
    "Питахайя": "Dragon fruit", "Слива": "Plum", "Тамаринд": "Tamarind", "Фейхоа": "Feijoa",
    "Финик": "Date", "Фрукты": "Fruit mix", "Хурма": "Persimmon", "Чернослив": "Prune",
    "Юдзу": "Yuzu", "Яблоко": "Apple",
    # creamy
    "Йогурт": "Yogurt", "Молоко": "Milk", "Сливочный": "Cream",
    # herbal
    "Алоэ": "Aloe", "Базилик": "Basil", "Древесный": "Woody", "Кактус": "Cactus",
    "Лемонграсс": "Lemongrass", "Мелисса": "Lemon balm", "Ревень": "Rhubarb",
    "Розмарин": "Rosemary", "Тархун": "Tarragon", "Травяной": "Herbs", "Чабрец": "Thyme",
    # vegetable
    "Кукуруза": "Corn", "Морковь": "Carrot", "Огурец": "Cucumber", "Перец": "Pepper",
    "Томат": "Tomato", "Тыква": "Pumpkin",
    # fresh
    "Жвачка": "Bubble gum", "Ментол": "Menthol", "Мята": "Mint", "Холодок": "Ice",
    "Эвкалипт": "Eucalyptus",
    # berry
    "Асаи": "Acai", "Барбарис": "Barberry", "Брусника": "Lingonberry", "Бузина": "Elderberry",
    "Виноград": "Grape", "Вишня": "Cherry", "Голубика": "Blueberry", "Гуарана": "Guarana",
    "Ежевика": "Blackberry", "Земляника": "Wild strawberry", "Ирга": "Serviceberry",
    "Кизил": "Cornelian cherry", "Клубника": "Strawberry", "Клюква": "Cranberry",
    "Княженика": "Arctic raspberry", "Красная смородина": "Redcurrant",
    "Крыжовник": "Gooseberry", "Малина": "Raspberry", "Морошка": "Cloudberry",
    "Облепиха": "Sea buckthorn", "Рябина": "Rowan", "Черемуха": "Bird cherry",
    "Черная смородина": "Blackcurrant", "Черника": "Bilberry", "Ягоды": "Berry mix",
    # dessert
    "Булочка": "Bun", "Ваниль": "Vanilla", "Вафли": "Waffles", "Выпечка": "Pastry",
    "Десерт": "Dessert", "Зефир": "Marshmallow", "Ириска": "Toffee", "Карамель": "Caramel",
    "Кекс": "Cake", "Кленовый": "Maple", "Конфетный": "Candy", "Леденцы": "Hard candy",
    "Мармелад": "Gummies", "Мороженое": "Ice cream", "Мёд": "Honey", "Печенье": "Cookie",
    "Пирог": "Pie", "Пончик": "Donut", "Пряник": "Gingerbread",
    "Сгущенка": "Condensed milk", "Тирамису": "Tiramisu", "Чизкейк": "Cheesecake",
    "Шоколад": "Chocolate",
    # spices
    "Анис": "Anise", "Имбирь": "Ginger", "Кардамон": "Cardamom", "Карри": "Curry",
    "Кашмир": "Kashmir", "Корица": "Cinnamon", "Лакрица": "Licorice", "Мастика": "Mastic",
    "Сандал": "Sandalwood", "Специи": "Spices", "Шалфей": "Sage", "Шафран": "Saffron",
    # alcohol
    "Абсент": "Absinthe", "Алкоголь": "Alcohol", "Амаретто": "Amaretto", "Апероль": "Aperol",
    "Бейлис": "Baileys", "Вино": "Wine", "Виски": "Whisky", "Водка": "Vodka",
    "Глинтвейн": "Mulled wine", "Дайкири": "Daiquiri", "Джин": "Gin",
    "Кайпиринья": "Caipirinha", "Коньяк": "Cognac", "Космополитен": "Cosmopolitan",
    "Куба либре": "Cuba libre", "Лимончелло": "Limoncello", "Маргарита": "Margarita",
    "Мохито": "Mojito", "Пиво": "Beer", "Пина колада": "Piña colada", "Портвейн": "Port",
    "Ром": "Rum", "Самбука": "Sambuca", "Сангрия": "Sangria", "Сидр": "Cider",
    "Текила": "Tequila", "Шампанское": "Champagne",
    # hot drinks
    "Зеленый чай": "Green tea", "Какао": "Cocoa", "Кофе": "Coffee", "Орчата": "Horchata",
    "Чай": "Tea", "Черный чай": "Black tea",
    # floral
    "Гвоздика": "Clove", "Жасмин": "Jasmine", "Лаванда": "Lavender", "Лотос": "Lotus",
    "Роза": "Rose", "Ромашка": "Chamomile", "Сакура": "Sakura", "Цветочный": "Floral",
    # cold drinks
    "Байкал": "Baikal soda", "Газировка": "Soda", "Квас": "Kvass", "Кола": "Cola",
    "Лимонад": "Lemonade", "Рутбир": "Root beer", "Тоник": "Tonic", "Энергетик": "Energy drink",
    # tobacco
    "Сигара": "Cigar", "Табачный": "Tobacco",
    # nuts
    "Арахис": "Peanut", "Кунжут": "Sesame", "Миндаль": "Almond", "Нуга": "Nougat",
    "Орех": "Nuts", "Фисташки": "Pistachio", "Халва": "Halva",
    # pine
    "Ёлка": "Christmas tree", "Кипарис": "Cypress", "Можжевельник": "Juniper",
    "Хвойный": "Pine",
    # other
    "Бустер": "Booster", "Парфюм": "Perfume",
    # savoury
    "Бекон": "Bacon", "Гастрономия": "Savoury", "Злаки": "Cereal", "Мясо": "Meat",
    "Овсянка": "Oatmeal", "Попкорн": "Popcorn", "Рис": "Rice", "Сыр": "Cheese",
    "Хлеб": "Bread", "Чеснок": "Garlic",
}
