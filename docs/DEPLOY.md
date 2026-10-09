# Put Booked online for friends (step by step, no coding)

You will get a link such as `https://booked-ab12.onrender.com`. Friends open it on their phone, take or upload shelf photos and get their books and Reader Identity. Every friend gets their own invite code, so you control who can use it and how much each person can scan.

Time: about 30 minutes. Cost: the hosting is free; scans cost the API money you cap yourself (a photo is roughly 1 to 3 cents).

You need three accounts: GitHub (you have one, the code is in `erelsherman/booked`), Anthropic (pays for reading the photos) and Render (runs the app).

## Step 1. Anthropic: get a key and set a hard money limit (do this first)

1. Go to **console.anthropic.com** and sign in or create an account.
2. Add a payment method and buy a small amount of credit, for example **$10**. **Leave auto-reload off.** When the credit is gone, scanning stops by itself.
3. Find the **spend limit** setting (look under Settings, then Limits or Billing) and set the monthly limit to **$10**. This is the limit that protects you no matter what else goes wrong.
4. Open **API keys**, press **Create key**, name it `booked`, and copy it (it starts with `sk-ant-`). You see it only once. Keep it in a note for step 3. Never send it to anyone, and never paste it into a chat or into the code.

## Step 2. Invent an invite code for each person

Make up a short random code per person, using letters and digits. Example:

`anna=k7x2m9,ben=q4w8p3,me=z5t6r1`

(name, equals sign, code; people separated by commas, no spaces). Each person's daily limit is counted by their code. You can add or remove people later.

## Step 3. Render: create the app

1. Go to **render.com** and sign up with **GitHub** (not Google: Render needs to read your code from GitHub, and this connects the two in one step). Allow it to see the `booked` repository.
2. Press **New**, then **Blueprint**, and choose the repository `erelsherman/booked`.
3. When it asks for a branch, choose **`claude/book-app-planning-78bhom`** (that is where the code is today).
4. Render reads the file `render.yaml` and shows a form with three empty fields. Fill them:
   - `ANTHROPIC_API_KEY`: the key from step 1.
   - `BOOKED_INVITE_CODES`: the line from step 2.
   - `BOOKED_CONTACT`: your email address.
5. Press **Apply** and wait about 5 minutes until the service says **Live**. Its address is shown at the top, for example `https://booked-ab12.onrender.com`.

## Step 4. Try it yourself

On your phone open: `https://<your address>/#token=<your code>`

Take or upload a shelf photo. If it asks for an invite code or says "missing or wrong invite code", the part after `#token=` is wrong.

## Step 5. Share

Send each friend their own link: `https://<your address>/#token=<their code>`. Tell them:
- the photos are sent to Anthropic to be read and are not saved by Booked;
- there is a daily limit per person (12 photos by default);
- it is an early test and some books will be wrong, and that is what you want to hear about.

## The limits that keep your costs capped

| Limit | Default | Where you change it |
|---|---|---|
| Photos per person per day | 12 | `BOOKED_PHOTOS_PER_PERSON_PER_DAY` |
| Photos per day, everyone | 60 | `BOOKED_PHOTOS_PER_DAY` |
| Spend per day | $1 | `BOOKED_MAX_DAILY_USD` |
| Spend per month | $5 | `BOOKED_MAX_SPEND_USD` |
| Spend limit at Anthropic | $10 | console.anthropic.com |

To change one: Render, your service, **Environment**, edit the value, **Save**.

**Be aware:** the free Render plan forgets the app's counters each time the app restarts or goes to sleep, which can happen several times a day. That means the first four rows can reset. The Anthropic limit in the last row cannot. Treat the app's limits as a politeness and the Anthropic limit as the real cap. If you want the app's counters to survive restarts, Render's paid plan with a small disk does it (set `BOOKED_STATE_DIR` to the disk's folder).

Other things on the free plan: the app sleeps after about 15 minutes without visitors, and the first visit afterwards takes around 30 seconds to wake it.

## Turning it off

- Pause: Render, your service, **Suspend**. The link stops working.
- Stop all spending immediately: in the Anthropic console, delete the `booked` key.
- Remove one person: delete their entry from `BOOKED_INVITE_CODES` and save.

## If something goes wrong

- "Missing or wrong invite code": the link is missing `#token=<code>`, or the code is not in `BOOKED_INVITE_CODES`.
- The service says **Failed**: open the service's **Logs** in Render and send me the last 20 lines.
- "Limit reached" messages are the limits working as designed.
- Not tested yet: this exact deployment (the Docker image has not been built, and the app has not run with a real key). Expect that the first attempt may need one fix; send me what Render shows.
