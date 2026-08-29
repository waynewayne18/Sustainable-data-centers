What a layer is

A layer is one number for every square of the country.

The country is 1300 squares tall and 700 wide. So a layer is a grid of 910,000 numbers. Most are sea, which we ignore. 230,044 are land.

You have one layer per thing you care about:

a carbon layer — how dirty the electricity is in each square
a farmland layer — how good the soil is in each square
a water layer — how scarce water is in each square

Every layer is the same size and lines up. Square 900 across, 500 down is the same field in every layer.

The arithmetic

Take one square. Row 900, column 500. That's real farmland in West Lindsey, Lincolnshire.

Step 1 — Is it allowed at all?

Check the exclusion layers. Flood zone? National park?

If yes: score is 0. Stop. Don't bother with the rest.

Ours isn't. Carry on.

Step 2 — Look up the raw numbers

Layer	This square	Country range
Carbon intensity	180	50 to 400
Curtailed energy	200	0 to 1000
Farmland grade	2	1 to 5
Water stress	4	1 to 5
Heat reuse	60	0 to 100

These can't be averaged. 180 and 2 aren't the same kind of number.

Step 3 — Squash everything to 0–1

Take the value. Subtract the lowest. Divide by the range.

Carbon: (180 − 50) ÷ 350 = 0.37

But low carbon is good, and we want 1 to always mean good. So flip it:

1 − 0.37 = 0.63

Do the same for the rest:

Layer	Sum	Result	Flipped?
Carbon	(180−50)÷350 = 0.37	0.63	yes, low is good
Curtailment	(200−0)÷1000 = 0.20	0.20	no, high is good
Farmland grade	(2−1)÷4 = 0.25	0.25	no, grade 5 soil is poor, so fine to build on
Water stress	(4−1)÷4 = 0.75	0.25	yes, low stress is good
Heat reuse	(60−0)÷100 = 0.60	0.60	no, high is good

That flipping is the higher_is_better setting in the code. Get one wrong and the map looks fine but is backwards.

Step 4 — Average within each theme

Energy has two layers: (0.63 + 0.20) ÷ 2 = 0.41

Land has one: 0.25

Water has one: 0.25

Community has one: 0.60

Step 5 — Average the four themes

(0.41 + 0.25 + 0.25 + 0.60) ÷ 4 = 0.38

That square scores 0.38.

Reading the result

0.38 is poor. Look at why: land 0.25 and water 0.25 dragged it down. Good farmland, scarce water.

That's the whole point of keeping four separate themes instead of one number. You can see what made a place score badly, not just that it did.

Repeat for all 230,044 land squares. That's the map.