
+++
date = '2026-08-16T12:25:56+01:00'
draft = false
title = 'Making it easy to track my diet via a web app'
tags = ["AI", "Agentic", "Agents", "Diet" ]
+++

I used an AI agent to build meal and workout plans that would help me lose weight and deployed it to Cloudflare pages
<!--more-->

## The problem

Back in my university days, I used to be super lean, workout everyday, and was able to remain motivated and stay fit.

As I was getting older, my metabolism started slowing down, and I had gotten injured a lot of times, and most importantly, got caught up in life.

All of these factors made me gain weight, and lose my motivation to get back in shape.

The difference was that back when I was younger, it was much easier to just go from slim to fit, as the process didn't involve losing weight at all. It was
just about training day after day, and the body responded quite nicely.


However now, I had to work my way backwards as I had gained over 20 Kgs from my university days, and trying to just raw-dogging it by trying to remember what I ate,
ballpark estimate the calories and refrain from certain stuff was just not working out for me. I was seeing no results, and just kept on gaining weight.

I think we all know that diets are no fun at all, and I personally think that it's super difficult to stay consistent, but to also remember what you should and should not
eat, how much you should/must eat, but also include enough things to not get bored, not starve yourself out if you have a big appetite like I do, but also not feel like you're in a
military boot camp and you have a sergeant yelling constantly at you and treating you like his bitch.


## Doing it the "conventional" way

Of course, this wasn't the first time I had tried to do this, and I think it's a "classic" problem that people try to solve.

It usually goes by making a google search on how to lose some weight, find some diet program, and try to follow that.

That stuff just doesn't really work well with me, and I can't really explain how, it felt like I needed some sort of process that just grouped it all in once place:
* The list of stuff I need to buy
* The meals I can prepare, with the portions
* The workout plan, because the purpose was to keep the muscle mass, and lose fat

I tried doing it this way twice or three times before, but it had never worked out.

So this made me wonder: What if I built a custom app that would:
* Give me daily meal plans, that change every day
* Gives me a list of ingredients to buy once and for all, enough stock for a week.
* Adapt it to my taste, so that it makes meals I'd be willing to eat.

I'm sure that there are apps that exist and do this already, but I figured this could be a fun project to do, and I write code for a living so why not ?

Moreover, we live in an era where agents can do this for us super easily, so why the heck not ?

## Making a diet tracking app


The requirements were the following:

* I wanted to maximize fat loss, and minimize muscle loss, without being too aggressive on myself
* I wanted a diverse, but no so boring diet, meals that changed weekly 
* I wanted the meals to be easy to make from both a time/prep and ingredient perspective
* I wanted the diet to be volume heavy, because I like to eat a lot
* I wanted to avoid going on an ingredient hunt at all costs, so only stuff I can almost find everywhere
* I wanted it to be high on fibers as well, for good transit
* Include sweet treats from time to time, because who doesn't like that

Now that I had the requirements in place, it was time to lay out how I imagined this would work:
* I wanted a web app that only I could access, deployed on some domain I own
* I wanted the app to list all the ingredients I need to buy for the entire week, as checkboxes I could tick to keep track
* I wanted the list of meals to shuffle every day, and have a button to shuffle either the entire day meal plan, or individual meals should I not feel like it.

The above resulted in the following initial prompt:

{{< code bash >}}

I want to build a web app that allows me to track my diet.

Here are the diet's requirements:

* I wanted to maximize fat loss, and minimize muscle loss, without being too aggressive on myself, so make it protein heavy
* I wanted a diverse, but no so boring diet, meals that changed weekly, preferably from a list of cuisines that I can chose: asian/italian/mexicain
* I wanted the meals to be easy to make from both a time/prep and ingredient perspective
* I wanted the diet to be volume heavy, but not high on calories, because I like to eat a lot
* I want the ingredients list to be super easy to find in most supermarkets
* Include sweet treats from time to time
* I wanted it to be high on fibers as well, for good transit. I have crackers that have these nutritional values per 100g: 46g carbs, 5g fat, 26g fiber. Include it in breakfasts and snacks


As for the app, i want it to do the following:

* I want a static site, deployed on cloudflare pages
* I want it so that only I could access it
* The app needs to allow me to change the weekly cuisine should I change my mind
* The app will list the weekly ingredients, with exact portions to buy. These might be persisted somwehre to be able to track what I bought and what I haven't yet, and resets every Sunday
* Randomize the meals per day, so that I don't eat the same thing everyday. And make it so that I can shuffle each meal individually should I feel like it.

{{< /code >}}


For deployment, I had [Cloudflare](https://www.cloudflare.com/) as my domain registrar, and I knew that they had
a solution called [Pages](https://pages.cloudflare.com/), so I thought this could be more than enough for what I wanted to do, and it fits nicely since it's all configured
in one place. As for persisting state, I used [Cloudflare Worker KV](https://developers.cloudflare.com/kv/), which is a simple key-value store.

For the curious ones, the application code can be found at the following [repository](https://github.com/shtlrs/operation-80).

This of course took a heuristic approach where I'd serve the content locally, test out the difference features before deploying and potentially fix issues.

Some of the issues were:
* Clicking a checkbox would immediately uncheck itself: The click event was fired twice - once from the row and once from the input inside it. Fixed by checking the origin of the event: `e.target.type === "checkbox" ? e.target.checked: undefined`
* The state was being saved, but not retrieved properly: This was a dumb AI moment where key construction was wrong, so just made it so that they to use to fetch data is as simple as the {section}/{date}, where section is either the ingredients list, workouts, other misc actions such as measuring my daily weight, etc.
* Sometimes the app would deploy in preview mode: This was because the wrangler CLI would check the branch you're in, and if it's not the main one, it won't deploy to production. I fixed this by having a `deploy.sh` script that would explicitly prompt me to which environment I'd like to deploy, regardless of the branch.
* The deploy version was not being rendered properly, and that's because it built a function that fetches the deployed version, but wasn't rendering it.


## Results

I've been doing this for 3 weeks now, and I'm losing the projected weight of 1Kg/Week.

The agent added a checkbox to check weight daily, but I felt that doing this on a weekly basis would yield greater satisfaction, so that's a part I wasn't using of the application.

There's still a long way to go, because the overall weight I'm trying to lose is 10Kgs, so that's 7 more weeks in total, but the road ahead seems solid as long as I keep my spirits high and do my best to follow the plan.

This was a fun project that I don't regret at all, even though I hardly spent 2 hours in total on it, mostly giving feedback to the agent about what's not working.

Whether this is worth it for others to do is a completely subjective topic, as things that don't work for me can work pretty well for others, and vice versa.
