"""
Generates products.xlsx — the P5 retail product catalogue.
65 products across kids, teens, women, men.
Each row has structured columns (SQL-filterable) + a natural-language description (vector/BM25).
Run: python generate_products.py
"""

import pandas as pd
from pathlib import Path

# Columns:
#   id, name, category, gender, colour, size, min_age, max_age, price, fabric, in_stock, description

rows = [

    # ── KIDS DRESSES ──────────────────────────────────────────────────────────
    (1,  "Ivory Lace Princess Frock",
         "dress", "girls", "white", "6-7Y", 5, 8, 650, "net", True,
         "A dreamy white net frock with delicate lace trim and a full princess skirt. "
         "Ideal for birthday parties, dance recitals, and festive celebrations. "
         "Soft cotton lining keeps little ones comfortable all day."),

    (2,  "White Puff-Sleeve Cotton Frock",
         "dress", "girls", "white", "8-9Y", 7, 10, 590, "cotton", True,
         "A breezy white cotton frock with puffed sleeves and a tiered skirt. "
         "Great for birthday parties, school events, and Sunday outings. "
         "Easy machine wash, stays bright after multiple washes."),

    (3,  "Pink Satin Party Frock",
         "dress", "girls", "pink", "8-9Y", 7, 10, 780, "satin", True,
         "Shimmery pink satin frock with a ribbon waistband and bow at the back. "
         "Designed for birthday parties, weddings, and festive occasions. "
         "Fully lined for comfort; the flared skirt twirls beautifully."),

    (4,  "Red Velvet Festive Frock",
         "dress", "girls", "red", "4-5Y", 3, 6, 580, "velvet", True,
         "Rich red velvet frock perfect for Christmas parties and festive gatherings. "
         "Gold trim at the collar and cuffs adds a celebratory touch. "
         "Pairs well with white tights and mary-jane shoes."),

    (5,  "Yellow Floral Sundress",
         "dress", "girls", "yellow", "2-3Y", 1, 4, 320, "cotton", True,
         "Cheerful yellow cotton sundress with a sunflower print throughout. "
         "Lightweight and breathable — great for summer picnics and casual outings. "
         "Adjustable shoulder straps for a flexible fit as toddlers grow."),

    (6,  "Blue Denim Pinafore Dress",
         "dress", "girls", "blue", "10-11Y", 9, 12, 490, "denim", True,
         "Classic blue denim pinafore that pairs with any t-shirt underneath. "
         "Roomy pockets and adjustable straps make it practical for school days and weekend outings. "
         "Sturdy denim that softens with every wash."),

    (7,  "Purple Silk Occasion Frock",
         "dress", "girls", "purple", "8-9Y", 7, 10, 850, "silk", True,
         "Elegant purple silk frock with a pleated skirt and embroidered neckline. "
         "Perfect for weddings, festive celebrations, and birthday parties. "
         "Gentle hand wash recommended to maintain the sheen."),

    (8,  "Peach Tulle Birthday Frock",
         "dress", "girls", "peach", "6-7Y", 5, 8, 720, "net", True,
         "Soft peach tulle frock with a sparkly bodice and layers of netting in the skirt. "
         "A top pick for birthday parties and princess-themed events. "
         "The elasticated waist ensures a comfortable fit without fuss."),

    (9,  "White Georgette Floral Frock",
         "dress", "girls", "white", "10-11Y", 9, 12, 940, "georgette", True,
         "Lightweight white georgette frock with a delicate floral print. "
         "Elegant enough for festive occasions, comfortable enough for everyday wear. "
         "The flowing silhouette looks beautiful on pre-teen girls."),

    (10, "Green Cotton Casual Dress",
         "dress", "girls", "green", "12-13Y", 11, 14, 520, "cotton", True,
         "Relaxed green cotton dress with a smocked bodice and a midi-length skirt. "
         "Versatile enough for casual outings, school events, and weekend brunches. "
         "Breathable cotton keeps girls cool and comfortable."),

    (11, "Navy A-Line School Dress",
         "dress", "girls", "navy", "8-9Y", 7, 10, 460, "cotton", True,
         "Neat navy blue A-line dress with a white Peter Pan collar. "
         "A polished choice for school events, annual days, and family gatherings. "
         "Easy-care cotton that holds its shape through active play."),

    (12, "Floral Midi Dress for Tweens",
         "dress", "girls", "multicolour", "12-13Y", 11, 14, 680, "rayon", True,
         "Vibrant floral midi dress in a lightweight rayon fabric. "
         "Perfect for birthday parties, casual hangouts, and summer outings. "
         "The wrap-style top flatters pre-teen silhouettes."),

    # ── KIDS TOPS & T-SHIRTS ──────────────────────────────────────────────────
    (13, "Lion Print Cotton T-Shirt",
         "tshirt", "boys", "yellow", "6-7Y", 5, 8, 290, "cotton", True,
         "Bold lion print on a sunny yellow cotton t-shirt that kids love. "
         "Soft, breathable fabric perfect for active play, school days, and weekend adventures. "
         "The durable print stays vivid after repeated washes."),

    (14, "Dinosaur Graphic Tee",
         "tshirt", "boys", "green", "4-5Y", 3, 6, 260, "cotton", True,
         "Fun green t-shirt featuring a roaring T-Rex graphic on the front. "
         "Toddler-friendly design with a tagless collar to avoid irritation. "
         "Great for park outings, playdates, and casual days at home."),

    (15, "Classic Striped Polo Shirt",
         "top", "boys", "blue", "8-9Y", 7, 10, 380, "cotton", True,
         "Smart navy and white striped polo shirt with a neat collar and button placket. "
         "A versatile piece for school photos, family outings, and smart-casual occasions. "
         "Holds its shape and colour through regular machine washes."),

    (16, "Cartoon Print Toddler Tee",
         "tshirt", "unisex", "red", "2-3Y", 1, 4, 240, "cotton", True,
         "Adorable red t-shirt with cheerful cartoon characters on the front. "
         "Ultra-soft cotton is gentle on toddler skin; flat seams prevent chafing. "
         "Easy pull-over style with a slightly stretchy neck opening."),

    (17, "White Basic Cotton Tee",
         "tshirt", "boys", "white", "10-11Y", 9, 12, 280, "cotton", True,
         "A clean white cotton t-shirt that layers under anything or works on its own. "
         "Comfortable, durable, and ideal for school uniforms or casual summer days. "
         "Pre-shrunk fabric so the fit stays consistent."),

    (18, "Pink Floral Printed Top",
         "top", "girls", "pink", "10-11Y", 9, 12, 360, "rayon", True,
         "Breezy pink rayon top with an all-over floral print and a flowy silhouette. "
         "Perfect for casual outings, birthday parties as a top, and school celebrations. "
         "Light enough for warm weather, pairs well with jeans or leggings."),

    (19, "Blue Tie-Dye Sweatshirt",
         "top", "boys", "blue", "12-13Y", 11, 14, 560, "cotton", True,
         "Cool tie-dye sweatshirt in blue and white tones with a relaxed fit. "
         "Great for weekend hangs, casual outings, and cooler evenings. "
         "Soft fleece interior provides warmth without bulk."),

    (20, "Graphic Print Hoodie",
         "top", "boys", "black", "12-13Y", 11, 14, 680, "cotton", True,
         "Black hoodie with a bold street-art graphic on the back and kangaroo pocket in front. "
         "A favourite for tweens who love a streetwear aesthetic at school or outings. "
         "Medium-weight cotton blend keeps it warm without overheating."),

    # ── KIDS ETHNIC WEAR ─────────────────────────────────────────────────────
    (21, "White Cotton Kurta Pyjama Set",
         "ethnic_set", "boys", "white", "6-7Y", 5, 8, 820, "cotton", True,
         "Crisp white cotton kurta and pyjama set with subtle thread embroidery at the neckline. "
         "Perfect for Eid, Diwali, weddings, and festive family gatherings. "
         "Breathable cotton keeps boys comfortable during long celebrations."),

    (22, "Pink Lehenga Choli with Dupatta",
         "lehenga", "girls", "pink", "6-7Y", 5, 8, 1250, "silk", True,
         "Pretty pink silk lehenga choli with intricate zari embroidery and a matching dupatta. "
         "A star choice for weddings, birthday parties, and festive occasions like Navratri. "
         "The flared lehenga skirt lets girls twirl freely and feel like a princess."),

    (23, "Yellow Anarkali Suit",
         "ethnic_set", "girls", "yellow", "8-9Y", 7, 10, 980, "georgette", True,
         "Sunshine yellow anarkali suit with a floor-grazing flared kurta and churidar bottoms. "
         "Ideal for weddings, Diwali celebrations, and school cultural programmes. "
         "Lightweight georgette fabric flows gracefully and keeps kids comfortable."),

    (24, "Blue Kurta Pyjama Set",
         "ethnic_set", "boys", "blue", "10-11Y", 9, 12, 720, "cotton", True,
         "Royal blue cotton kurta with a mandarin collar and self-print texture, paired with matching pyjama. "
         "A festive yet comfortable choice for Eid, weddings, and family celebrations. "
         "Easy to move in — boys can enjoy festivities without feeling restricted."),

    (25, "Red Lehenga Set for Toddlers",
         "lehenga", "girls", "red", "4-5Y", 3, 6, 1100, "silk", True,
         "Vibrant red silk lehenga choli adorned with golden embroidery — perfect for little ones at weddings and birthday parties. "
         "Fully lined for skin comfort; the elasticated waistband makes it easy to wear. "
         "Comes with a matching dupatta for a complete traditional look."),

    # ── TEEN CLOTHING ─────────────────────────────────────────────────────────
    (26, "White Lace Crop Top",
         "top", "girls", "white", "S", 14, 17, 480, "cotton", True,
         "Delicate white lace crop top with a scalloped hem, designed for teenage girls. "
         "Pairs beautifully with high-waist jeans or skirts for casual outings and birthday parties. "
         "The stretchy fabric offers a comfortable, flattering fit."),

    (27, "Black Skinny Jeans",
         "jeans", "girls", "black", "S", 14, 17, 920, "denim", True,
         "Classic black skinny jeans with a slight stretch for ease of movement. "
         "A wardrobe staple for teens — works with everything from graphic tees to blouses. "
         "High-rise waist and ankle-length cut for a sleek, on-trend silhouette."),

    (28, "Blue Ripped Skinny Jeans",
         "jeans", "girls", "blue", "S", 14, 17, 980, "denim", True,
         "Trendy light-wash blue jeans with strategic rips at the knee for a streetwear vibe. "
         "Slim fit with slight stretch makes them comfortable for all-day wear. "
         "A must-have for teens who love casual-chic style."),

    (29, "Floral Midi Skirt",
         "skirt", "girls", "multicolour", "S", 14, 17, 690, "rayon", True,
         "Dreamy floral midi skirt in a floaty rayon fabric with an elasticated waistband. "
         "Perfect for casual outings, birthday lunches, and summer hangouts with friends. "
         "The bold floral print pops against neutral tops."),

    (30, "Olive Cargo Pants",
         "pants", "boys", "olive", "M", 14, 17, 790, "cotton", True,
         "Relaxed-fit olive cargo pants with multiple functional pockets for teens who are always on the move. "
         "Durable cotton twill fabric holds up through outdoor adventures and casual hangouts. "
         "Pairs effortlessly with hoodies, tees, and sneakers."),

    (31, "Oversized Cozy Hoodie",
         "top", "unisex", "grey", "M", 14, 17, 780, "cotton", True,
         "Super-soft grey oversized hoodie with a fleece interior for maximum warmth and comfort. "
         "The ultimate loungewear piece — great for lazy weekends, cool evenings, and casual school days. "
         "Roomy kangaroo pocket and a slouchy fit that teens love."),

    (32, "Striped Ribbed Tank Top",
         "top", "girls", "white", "S", 14, 17, 390, "cotton", True,
         "Fitted white and beige striped ribbed tank top with a scoop neck. "
         "A versatile wardrobe basic that layers under jackets or stands alone in summer. "
         "Soft, breathable cotton keeps it comfortable for all-day wear."),

    (33, "Graphic Oversized Tee",
         "tshirt", "boys", "black", "M", 14, 17, 510, "cotton", True,
         "Oversized black tee with a bold typographic graphic print — a streetwear staple for teenage boys. "
         "Heavyweight cotton gives structure while staying soft. "
         "Tuck it into jeans or let it hang loose for a relaxed look."),

    # ── WOMEN'S CLOTHING ──────────────────────────────────────────────────────
    (34, "White Floral Maxi Dress",
         "dress", "women", "white", "M", 18, 50, 1490, "rayon", True,
         "Effortlessly elegant white maxi dress with an all-over floral print and a tiered skirt. "
         "A go-to for beach holidays, brunch dates, and garden parties. "
         "The adjustable tie waist flatters all body types."),

    (35, "Black Wrap Cocktail Dress",
         "dress", "women", "black", "S", 18, 45, 2250, "crepe", True,
         "Sophisticated black wrap dress in a structured crepe fabric with a V-neckline. "
         "Perfect for cocktail parties, work dinners, and evening events. "
         "The wrap silhouette is universally flattering and timeless."),

    (36, "Navy Blue Midi Shirt Dress",
         "dress", "women", "navy", "M", 18, 45, 1380, "linen", True,
         "Relaxed navy linen shirt dress with button-down front and rolled-tab sleeves. "
         "A smart-casual favourite for work-from-home days, coffee meetings, and weekend outings. "
         "Linen keeps you cool and gets better-looking with wear."),

    (37, "Red Ruffle Wrap Dress",
         "dress", "women", "red", "M", 18, 45, 1350, "georgette", True,
         "Vibrant red georgette wrap dress with ruffle detailing at the hem. "
         "Ideal for date nights, festive parties, and celebratory dinners. "
         "Lightweight and breathable — comfortable even through a long evening."),

    (38, "Beige Linen Straight Kurta",
         "kurta", "women", "beige", "M", 18, 55, 920, "linen", True,
         "Minimalist beige linen kurta with subtle hand-block print and a straight silhouette. "
         "A daily-wear favourite that feels cool, relaxed, and effortlessly put-together. "
         "Pairs beautifully with palazzos, leggings, or straight-fit trousers."),

    (39, "Navy Blue Printed Cotton Kurta",
         "kurta", "women", "navy", "L", 18, 55, 780, "cotton", True,
         "Comfortable navy blue cotton kurta with a geometric block print and three-quarter sleeves. "
         "Great for office casual, college days, and everyday errands — breathable and easy to care for. "
         "Available in regular and plus sizes."),

    (40, "Multicolour Floral Anarkali Kurta",
         "kurta", "women", "multicolour", "S", 18, 45, 1150, "georgette", True,
         "Flowing anarkali-style kurta in a bold floral print on georgette fabric. "
         "Festive yet approachable — works for family functions, Diwali celebrations, and semi-formal events. "
         "The flared silhouette is flattering and movement-friendly."),

    (41, "White Broderie Anglaise Blouse",
         "top", "women", "white", "M", 18, 50, 680, "cotton", True,
         "Delicate white cotton blouse with broderie anglaise embroidery at the neckline and sleeves. "
         "An elegant wardrobe classic for office wear, brunches, and garden parties. "
         "Tuck into trousers for a polished look or wear loose over denim."),

    (42, "Black Wide-Leg Palazzo Pants",
         "pants", "women", "black", "M", 18, 55, 720, "crepe", True,
         "Flowy black crepe palazzo pants with an elasticated waist for all-day comfort. "
         "A versatile bottom that dresses up with a blouse or down with a basic tee. "
         "The wide-leg silhouette is flattering and endlessly comfortable."),

    (43, "Teal Embroidered Jacket Kurta Set",
         "ethnic_set", "women", "teal", "M", 18, 50, 2100, "silk", True,
         "Rich teal silk kurta paired with embroidered jacket and straight pants — a complete festive set. "
         "Perfect for weddings, cocktail functions, and Diwali celebrations. "
         "Intricate thread embroidery on the jacket adds a luxe, festive touch."),

    (44, "Cream Linen Co-ord Set",
         "top", "women", "cream", "S", 18, 45, 1680, "linen", True,
         "Matching cream linen top and wide-leg trouser set — minimal, chic, and effortless. "
         "Ideal for beach holidays, resort wear, and summer brunches. "
         "Natural linen gets softer and more beautiful with every wash."),

    (45, "Burgundy Velvet Evening Top",
         "top", "women", "burgundy", "S", 18, 40, 990, "velvet", True,
         "Luxurious burgundy velvet top with a square neckline and puff sleeves. "
         "A festive wardrobe hero for parties, dinners, and New Year celebrations. "
         "Pairs beautifully with black trousers or a silk midi skirt."),

    # ── MEN'S CLOTHING ────────────────────────────────────────────────────────
    (46, "White Oxford Cotton Shirt",
         "shirt", "men", "white", "M", 18, 55, 950, "cotton", True,
         "Crisp white Oxford cotton shirt with a button-down collar and single-button cuffs. "
         "A boardroom essential and weekend staple — pairs with suits or dark jeans. "
         "Non-iron finish keeps it looking sharp through long workdays."),

    (47, "Blue Slim-Fit Jeans",
         "jeans", "men", "blue", "32", 18, 50, 1350, "denim", True,
         "Classic mid-wash blue denim jeans with a slim but not skinny leg. "
         "Comfortable for all-day wear — great for casual Fridays, weekend outings, and travel. "
         "Slight stretch in the fabric prevents stiffness and allows free movement."),

    (48, "Black Straight-Fit Jeans",
         "jeans", "men", "black", "30", 18, 45, 1190, "denim", True,
         "Versatile black straight-cut jeans that dress up or down with ease. "
         "Works with everything — formal shirts, printed tees, or hoodies. "
         "Durable denim with a comfortable mid-rise waistband."),

    (49, "Olive Cargo Shorts",
         "shorts", "men", "olive", "M", 18, 40, 690, "cotton", True,
         "Rugged olive cotton cargo shorts with six pockets and a drawstring waist. "
         "Built for outdoor adventures, beach trips, and relaxed summer days. "
         "Lightweight twill fabric dries quickly after water activities."),

    (50, "White Pique Polo T-Shirt",
         "tshirt", "men", "white", "L", 18, 50, 620, "cotton", True,
         "Classic white pique polo shirt with ribbed collar and a two-button placket. "
         "Smartly casual — works for golf, office-casual Fridays, and weekend brunches. "
         "Pre-shrunk cotton holds its shape and stays bright wash after wash."),

    (51, "Grey Cotton Kurta",
         "kurta", "men", "grey", "M", 18, 55, 820, "cotton", True,
         "Understated grey cotton kurta with a subtle self-weave texture and a mandarin collar. "
         "Comfortable and stylish for festive occasions, casual Fridays, and family gatherings. "
         "Pairs with churidar, pyjama, or straight-fit trousers."),

    (52, "Navy Blue Zip-Up Hoodie",
         "top", "men", "navy", "L", 18, 45, 1150, "cotton", True,
         "Versatile navy blue hoodie with a full-length zip, fleece interior, and two front pockets. "
         "A go-to for chilly mornings, casual outings, and light outdoor activity. "
         "The slim fit looks polished without feeling restrictive."),

    (53, "Red and Black Checkered Flannel Shirt",
         "shirt", "men", "red", "M", 18, 50, 890, "cotton", True,
         "Classic red and black buffalo-check flannel shirt — warm, rugged, and effortlessly cool. "
         "Perfect for outdoor weekends, camping trips, and casual winter layering. "
         "Soft-brushed interior gets cosier with every wash."),

    # ── JACKETS & OUTERWEAR ───────────────────────────────────────────────────
    (54, "Pink Quilted Kids Jacket",
         "jacket", "girls", "pink", "8-9Y", 7, 10, 1150, "polyester", True,
         "Lightweight pink quilted jacket that provides warmth without adding bulk. "
         "Designed for cool winter mornings, school commutes, and outdoor play in the cold. "
         "Packs small enough to fit in a school bag when the day warms up."),

    (55, "Navy Puffer Jacket for Boys",
         "jacket", "boys", "navy", "10-11Y", 9, 12, 1280, "polyester", True,
         "Warm navy puffer jacket with a hood and secure zip pockets. "
         "Insulated fill keeps boys cosy on cold school mornings and winter outdoor activities. "
         "Water-resistant outer shell handles light rain and wind."),

    (56, "Black Bomber Jacket",
         "jacket", "unisex", "black", "M", 14, 25, 1650, "polyester", True,
         "Sleek black bomber jacket with ribbed cuffs and collar — a streetwear classic. "
         "Lightweight enough for autumn evenings but warm enough for mild winters. "
         "Pairs with everything from joggers to tailored trousers."),

    (57, "Beige Belted Trench Coat",
         "jacket", "women", "beige", "M", 18, 45, 2950, "cotton", True,
         "Timeless beige trench coat with a double-breasted front and belted waist. "
         "An investment piece that elevates any outfit — perfect for office commutes, travel, and formal occasions. "
         "Water-resistant cotton gabardine handles light showers with ease."),

    (58, "Olive Puffer Jacket for Men",
         "jacket", "men", "olive", "L", 18, 50, 2350, "polyester", True,
         "Chunky olive puffer jacket with a detachable hood and deep zip pockets. "
         "Premium insulation keeps you warm through cold winters, hill stations, and outdoor adventures. "
         "Durable ripstop outer shell resists snags and abrasion."),

    (59, "Red Hooded Windcheater",
         "jacket", "unisex", "red", "6-7Y", 5, 10, 820, "polyester", True,
         "Bright red windcheater with a hood and reflective strip at the back — great for outdoor safety. "
         "Lightweight and packable for school sports days, nature walks, and drizzly mornings. "
         "Wind and water-resistant outer layer keeps kids dry and warm."),

    (60, "Grey Wool-Blend Overcoat",
         "jacket", "women", "grey", "S", 18, 45, 3400, "wool", True,
         "Sophisticated grey wool-blend overcoat with a notch lapel and concealed button closure. "
         "A timeless statement piece for winter office wear, city commutes, and formal occasions. "
         "The half-belt at the back defines the waist for a flattering silhouette."),

    # ── JEANS & BOTTOMS ───────────────────────────────────────────────────────
    (61, "Blue High-Rise Skinny Jeans",
         "jeans", "women", "blue", "M", 18, 45, 1190, "denim", True,
         "Classic blue high-rise skinny jeans that flatter and elongate the legs. "
         "Comfortable stretch denim moves with you — great for all-day wear, brunches, and casual office days. "
         "Ankle-length cut looks polished with heels or sneakers alike."),

    (62, "Black Wide-Leg Trousers",
         "pants", "women", "black", "M", 18, 55, 1020, "crepe", True,
         "Elegant black wide-leg trousers in flowing crepe fabric with a high-rise elasticated waist. "
         "A comfortable yet sophisticated alternative to jeans — perfect for office, dinners, and events. "
         "Drapes beautifully and pairs with tucked-in blouses or crop tops."),

    (63, "Khaki Slim-Fit Joggers",
         "pants", "men", "khaki", "M", 18, 45, 680, "cotton", True,
         "Khaki slim-fit jogger pants with an elasticated waistband, cuffed hem, and side pockets. "
         "Comfortable enough for lounging at home but smart enough for a quick coffee run. "
         "Cotton-rich fabric stays breathable through warm days."),

    (64, "Blue Denim Shorts",
         "shorts", "boys", "blue", "M", 14, 17, 590, "denim", True,
         "Classic blue denim shorts with a five-pocket design and a straight leg. "
         "A summer essential for teenage boys — pairs with any tee for a laid-back look. "
         "Durable denim holds up through sports, outings, and outdoor adventures."),

    (65, "White Cotton Palazzo Pants",
         "pants", "women", "white", "M", 18, 55, 750, "cotton", True,
         "Breezy white cotton palazzo pants with a wide leg and elasticated waist. "
         "The ultimate summer comfort piece — cool, light, and effortlessly stylish. "
         "Pairs with kurtas, crop tops, or fitted blouses for a versatile wardrobe."),
]

columns = [
    "id", "name", "category", "gender", "colour",
    "size", "min_age", "max_age", "price", "fabric", "in_stock", "description"
]

df = pd.DataFrame(rows, columns=columns)

out = Path(__file__).parent / "products.xlsx"
df.to_excel(out, index=False, engine="openpyxl")
print(f"Wrote {len(df)} products → {out}")
print(df[["id","name","colour","size","min_age","max_age","price"]].to_string(index=False))
