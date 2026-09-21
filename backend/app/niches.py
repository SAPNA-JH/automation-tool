"""Niche preset library + AI niche creator.

A niche = brand voice + content pillars. In the multi-tenant app each user has their own
studio (stored per-user in the DB), so applying a niche returns the {brand, categories} to
persist — it no longer touches any global file. The AI creator builds the same structure
for ANY topic the user types.
"""
from __future__ import annotations

from .providers import llm

# The full template catalogue every studio can use (poster + reel designs).
DEFAULT_FORMATS = {
    "templates": [
        "grid", "grid-light", "grid-list", "grid-polaroid", "grid-steps", "grid-checklist",
        "grid-neon", "grid-mag", "grid-ranking", "vs", "vs-split", "this-or-that",
        "before-after", "overlay-classic", "overlay-center", "overlay-band", "overlay-tweet",
        "overlay-polaroid", "overlay-editorial", "quote-serif", "quote-neon", "did-you-know",
        "affirmation", "qna-sticker", "stat-hero", "definition-card",
        "reel-quote", "reel-slides", "reel-facts", "reel-story", "reel-countdown", "reel-vs",
    ],
    "grid_items": 6,
    "vs_rows": 5,
}


def _cats(*pairs) -> list[dict]:
    return [
        {"name": name, "weight": weight, "description": desc, "themes": themes}
        for name, weight, desc, themes in pairs
    ]


PRESETS: dict[str, dict] = {
    "glitch-life": {
        "name": "Glitch Life",
        "emoji": "🌒",
        "tagline": "The quiet ache of modern life — raw, honest, moody.",
        "accent": "#a855f7",
        "brand": {
            "niche": "the glitch in modern life — raw, honest reflections on feeling stuck, disconnected, numb, and overstimulated in today's world",
            "voice": "raw, honest, poetic-but-punchy; empathetic and a little provocative; short lines, no toxic positivity",
            "audience": "gen z and millennials who sense that modern life is subtly broken",
            "visual_style": "moody cinematic photography, muted desaturated tones, soft film grain, melancholic natural light, shallow depth of field, no text in image",
        },
        "categories": _cats(
            ("Stuck on Autopilot", 1, "Stagnation and the rat race. Tone: knowing, restless.",
             ["Living on autopilot without noticing", "Sunday night dread", "Busy but going nowhere", "Waiting for life to start"]),
            ("Screen Static", 1, "Digital overwhelm and dopamine burnout. Tone: self-aware, haunted.",
             ["Doomscrolling at 2am", "The comparison spiral", "Dopamine burnout", "A thousand connections, zero closeness"]),
            ("Signal Lost", 1, "Broken and fading relationships. Tone: tender, aching.",
             ["Friendships that quietly faded", "Being left on read", "Growing apart without a goodbye", "Surrounded by people, still unseen"]),
            ("Touch-Starved", 1, "Disrupted intimacy, framed emotionally — never explicit. Tone: vulnerable.",
             ["Craving closeness but fearing it", "The walls we build to stay safe", "Touch-starved in a swipe culture", "Wanting to be truly known"]),
            ("Dying Green", 1, "Eco-anxiety and the fading natural world. Tone: mournful, awake.",
             ["Concrete swallowing the green", "Seasons that don't feel right anymore", "Nature we only see on a screen", "Buying things to fill an empty space"]),
            ("Mental Static", 1, "Anxiety, burnout, numbness. Tone: honest, gentle.",
             ["The 3am overthinking spiral", "Tired but wired", "Burnout that sleep can't fix", "Going numb just to get through"]),
            ("Who Am I Anyway", 1, "Identity and meaning crisis. Tone: searching, quietly profound.",
             ["The self you perform online", "Drifting from who you used to be", "What is all of this even for", "Wearing a mask you forgot to take off"]),
            ("Glitch in the System", 1, "Late-capitalism fatigue. Tone: sharp, a little rebellious.",
             ["Measuring your worth in productivity", "The game feels rigged", "Working to afford a life you never live", "Rest reframed as laziness"]),
            ("Soft Reboot", 2, "The hopeful antidote — small human resets. Tone: warm, grounded.",
             ["One real conversation over a hundred likes", "Logging off to log back in", "Small analog joys", "Choosing presence over performance"]),
        ),
    },
    "motivation": {
        "name": "Daily Motivation",
        "emoji": "🔥",
        "tagline": "Discipline, mindset, and momentum for ambitious people.",
        "accent": "#f59e0b",
        "brand": {
            "niche": "daily motivation, discipline and winning mindsets for ambitious people",
            "voice": "direct, energizing, no-excuses but never cruel; short punchy lines; speaks to the person you're becoming",
            "audience": "18-35 year olds building careers, businesses and better habits",
            "visual_style": "high-contrast dramatic photography, sunrise runs, city grind, gym light rays, cinematic teal-orange grade, no text in image",
        },
        "categories": _cats(
            ("Discipline Over Motivation", 2, "Systems beat feelings. Tone: firm, clear.",
             ["Showing up when you don't feel like it", "Winning the morning", "Small reps compound", "Do it tired"]),
            ("Mindset Shifts", 1, "Reframes that unlock action. Tone: sharp, aha-moment.",
             ["Failure as tuition", "Comparison is a thief", "Play long games", "Your inputs become you"]),
            ("Beat Procrastination", 1, "Practical anti-procrastination. Tone: tactical.",
             ["The 5-minute start rule", "Eat the frog first", "Kill perfectionism", "Deadlines as allies"]),
            ("Success Habits", 1, "Routines of high performers. Tone: aspirational, concrete.",
             ["Morning routines that work", "Deep work blocks", "Digital sunset", "Weekly review ritual"]),
            ("Comeback Energy", 1, "Resilience after setbacks. Tone: warm, fierce.",
             ["Starting over stronger", "Rock bottom as foundation", "Quiet comebacks", "Proving yourself right"]),
        ),
    },
    "fitness": {
        "name": "Fitness & Training",
        "emoji": "💪",
        "tagline": "Workouts, form, recovery — results without gimmicks.",
        "accent": "#ef4444",
        "brand": {
            "niche": "no-nonsense fitness — training, recovery and consistency for real bodies and busy lives",
            "voice": "encouraging coach energy; evidence-aware, anti-gimmick; celebrates showing up",
            "audience": "beginners and returners 20-45 who want sustainable strength and health",
            "visual_style": "clean gym and outdoor training photography, natural sweat and effort, bright honest light, diverse bodies, no text in image",
        },
        "categories": _cats(
            ("Training Smart", 1, "Programming and form basics. Tone: practical coach.",
             ["Progressive overload explained simply", "Form beats ego lifting", "Full body vs splits", "The only 5 lifts you need"]),
            ("No-Gym Workouts", 1, "Home and outdoor training. Tone: accessible.",
             ["10-minute no-equipment burners", "Desk-break mobility", "Walking is underrated", "Hotel room workouts"]),
            ("Recovery Matters", 1, "Sleep, rest days, mobility. Tone: permission-giving.",
             ["Muscles grow on rest days", "Sleep is a PED", "Deload weeks", "Stretching that actually helps"]),
            ("Consistency Game", 2, "Habit side of fitness. Tone: warm, realistic.",
             ["Two workouts a week still counts", "Never miss twice", "Motivation follows action", "Your future body thanks you"]),
            ("Myth Busting", 1, "Fitness misinformation. Tone: friendly debunker.",
             ["Spot reduction is a myth", "Lifting won't make you bulky overnight", "Soreness isn't progress", "Cardio doesn't kill gains"]),
        ),
    },
    "nutrition": {
        "name": "Food & Nutrition",
        "emoji": "🥗",
        "tagline": "Simple recipes, honest nutrition, no diet drama.",
        "accent": "#22c55e",
        "brand": {
            "niche": "practical nutrition and simple healthy eating — flexible, evidence-based, zero diet-culture shame",
            "voice": "warm, practical, anti-fad; food is joy and fuel; small swaps over strict rules",
            "audience": "busy people who want to eat better without obsessing",
            "visual_style": "bright appetizing food photography, natural daylight, rustic wooden tables, colorful whole ingredients, no text in image",
        },
        "categories": _cats(
            ("Simple Swaps", 2, "Easy upgrades to everyday eating. Tone: friendly.",
             ["Protein at breakfast", "Fiber is the underrated hero", "Smart snack swaps", "Half your plate rule"]),
            ("Quick Meals", 1, "Fast healthy recipes. Tone: practical.",
             ["15-minute high-protein dinners", "One-pan wonders", "Meal prep for people who hate meal prep", "5-ingredient lunches"]),
            ("Nutrition Myths", 1, "Debunking diet noise. Tone: calm expert.",
             ["Carbs are not the enemy", "Detox teas don't detox", "Eating late doesn't auto-gain", "Superfoods are just foods"]),
            ("Mindful Eating", 1, "Relationship with food. Tone: gentle.",
             ["Eating without a screen", "Hunger vs boredom", "No food is a moral failing", "Slow meals, better signals"]),
        ),
    },
    "finance": {
        "name": "Personal Finance",
        "emoji": "💸",
        "tagline": "Money basics, saving, investing — calm and jargon-free.",
        "accent": "#10b981",
        "brand": {
            "niche": "personal finance made calm and simple — budgeting, saving, investing basics and money psychology (educational, not financial advice)",
            "voice": "clear, reassuring, jargon-free; numbers made human; no get-rich-quick energy",
            "audience": "20s-30s getting their money life together",
            "visual_style": "clean minimal lifestyle photography, coffee and notebooks, calm neutral tones with green accents, subtle wealth-adjacent scenes, no text in image",
        },
        "categories": _cats(
            ("Money Basics", 2, "Foundations: budgets, emergency funds. Tone: friendly teacher.",
             ["Pay yourself first", "The 50/30/20 starting point", "Emergency fund before investing", "Automate the boring parts"]),
            ("Investing Simply", 1, "Long-term investing basics. Tone: calm, educational.",
             ["Compound interest is magic", "Time in market beats timing", "Index funds explained", "Start small, start now"]),
            ("Money Psychology", 1, "Behavior and emotions around money. Tone: insightful.",
             ["Lifestyle creep is silent", "Emotional spending triggers", "Money scripts from childhood", "Comparison is expensive"]),
            ("Spending Smarter", 1, "Cutting waste without misery. Tone: practical.",
             ["Subscription audit day", "The 24-hour purchase rule", "Cook one more meal a week", "Buy it nice or buy it twice"]),
        ),
    },
    "psychology": {
        "name": "Psychology & Mind",
        "emoji": "🧠",
        "tagline": "How your brain actually works — biases, habits, emotions.",
        "accent": "#6366f1",
        "brand": {
            "niche": "everyday psychology — cognitive biases, habits, emotions and human behavior explained simply",
            "voice": "curious, precise, lightly playful; makes science feel personal; never diagnoses",
            "audience": "curious minds who love understanding themselves and others",
            "visual_style": "conceptual minimal photography, silhouettes and shadows, symbolic objects, deep blues and purples, thoughtful mood, no text in image",
        },
        "categories": _cats(
            ("Cognitive Biases", 1, "Mental shortcuts that mislead us. Tone: aha-moment.",
             ["Confirmation bias in daily life", "The spotlight effect", "Sunk cost trap", "Negativity bias"]),
            ("Habit Science", 1, "How habits form and change. Tone: practical science.",
             ["Cue, craving, response, reward", "Environment beats willpower", "Habit stacking", "The two-day rule"]),
            ("Emotions Decoded", 1, "Understanding feelings. Tone: warm, validating.",
             ["Naming emotions tames them", "Anger as a messenger", "Why we cry at kindness", "Anxiety's false alarms"]),
            ("Social Psychology", 1, "How people influence people. Tone: fascinating.",
             ["Mirroring and rapport", "Why crowds go silent", "The liking gap", "First impressions science"]),
            ("Mind Care", 2, "Gentle mental health maintenance. Tone: supportive, non-clinical.",
             ["Rest is cognitive maintenance", "Journaling as a brain dump", "The power of one good friend", "Sunlight and mood"]),
        ),
    },
    "tech-ai": {
        "name": "Tech & AI",
        "emoji": "🤖",
        "tagline": "AI, gadgets and the future — explained for humans.",
        "accent": "#06b6d4",
        "brand": {
            "niche": "technology and AI explained for everyday humans — trends, tools, and what they mean for your life and work",
            "voice": "smart but never condescending; excited yet balanced; cuts hype with clarity",
            "audience": "professionals and enthusiasts keeping up with tech without a CS degree",
            "visual_style": "sleek futuristic photography, neon-lit devices, server rooms, holographic vibes, cyan and deep navy palette, no text in image",
        },
        "categories": _cats(
            ("AI Explained", 2, "AI concepts made simple. Tone: clear translator.",
             ["What LLMs actually do", "AI agents in plain words", "Prompting as a skill", "Where AI still fails"]),
            ("Tools & Productivity", 1, "Tech that saves time. Tone: practical.",
             ["Automate your busywork", "Underrated apps", "Keyboard-first workflows", "One tool, one job"]),
            ("Future Watch", 1, "Where tech is heading. Tone: thoughtful futurist.",
             ["Jobs AI will change first", "The next interface after screens", "Robots in daily life", "Tech predictions scorecard"]),
            ("Digital Life", 1, "Living well with technology. Tone: balanced.",
             ["Own your attention", "Privacy basics everyone skips", "Digital declutter", "Screen time with intention"]),
        ),
    },
    "travel": {
        "name": "Travel & Places",
        "emoji": "✈️",
        "tagline": "Destinations, hacks, and the art of wandering.",
        "accent": "#0ea5e9",
        "brand": {
            "niche": "travel inspiration and practical wanderlust — destinations, budget hacks and traveling deeper not just farther",
            "voice": "wanderlust-warm, vivid, practical; sells the feeling and hands you the how",
            "audience": "young travelers and dreamers planning their next escape",
            "visual_style": "breathtaking golden-hour landscapes, tiny human in vast scenery, turquoise water, mountain mist, airport moments, no text in image",
        },
        "categories": _cats(
            ("Hidden Gems", 2, "Underrated destinations. Tone: insider secret.",
             ["Europe beyond the postcards", "Asia's quiet corners", "Small towns that feel like movies", "Shoulder-season magic"]),
            ("Travel Hacks", 1, "Cheaper, smoother trips. Tone: savvy friend.",
             ["Flight deal hunting", "Pack in a carry-on forever", "Airport survival kit", "Local eats over tourist traps"]),
            ("Solo & Slow", 1, "Solo and slow travel. Tone: encouraging.",
             ["First solo trip courage", "Staying longer, seeing deeper", "Digital nomad basics", "Traveling alone, never lonely"]),
            ("Wander Wisdom", 1, "Travel as perspective. Tone: reflective.",
             ["What leaving home teaches", "Collect moments not things", "Getting lost on purpose", "Coming home different"]),
        ),
    },
    "books": {
        "name": "Books & Reading",
        "emoji": "📚",
        "tagline": "Recommendations, lessons, and the reading life.",
        "accent": "#b45309",
        "brand": {
            "niche": "books, reading culture and big ideas from great pages — recommendations, lessons and the reading life",
            "voice": "cozy, literate, generous; a well-read friend who never gatekeeps",
            "audience": "readers and aspiring readers who love ideas and book aesthetics",
            "visual_style": "warm cozy photography, stacked books, rainy windows, coffee and blankets, golden lamp light, libraries, no text in image",
        },
        "categories": _cats(
            ("Book Lists", 2, "Curated recommendations. Tone: enthusiastic curator.",
             ["Books that rewire your brain", "Fiction that feels like therapy", "One-sitting reads", "Books everyone quotes but few finish"]),
            ("Lessons From Pages", 1, "Ideas from great books. Tone: distilled wisdom.",
             ["Atomic Habits in five lines", "Stoic lessons for modern chaos", "What novels teach about people", "Old books, current problems"]),
            ("Reading Life", 1, "The habit and joy of reading. Tone: cozy.",
             ["Reading before phone", "The 20-page rule", "DNF without guilt", "Building a reading ritual"]),
            ("Writer's Mind", 1, "On writing and creativity. Tone: inspiring craft.",
             ["Write badly first", "Notebooks of famous writers", "Reading like a writer", "Ideas are cheap, drafts are gold"]),
        ),
    },
    "business": {
        "name": "Business & Startup",
        "emoji": "🚀",
        "tagline": "Entrepreneurship, marketing, and building things people want.",
        "accent": "#f97316",
        "brand": {
            "niche": "entrepreneurship and modern business — startups, marketing, audience building and lessons from builders",
            "voice": "sharp operator energy; real talk over hustle porn; frameworks and stories",
            "audience": "founders, freelancers and side-hustlers building something of their own",
            "visual_style": "modern workspace photography, whiteboards and laptops, city offices at dusk, founder desk scenes, warm focused light, no text in image",
        },
        "categories": _cats(
            ("Startup Lessons", 1, "Hard-won founder wisdom. Tone: been-there mentor.",
             ["Launch before you're ready", "Talk to users weekly", "Default alive or default dead", "Niches get riches"]),
            ("Marketing That Works", 2, "Practical growth and brand. Tone: tactical.",
             ["Hooks are 80% of content", "Email is undefeated", "Show the process, sell the outcome", "One channel done well"]),
            ("Money & Models", 1, "Business models and pricing. Tone: clear-eyed.",
             ["Charge more, apologize less", "Recurring revenue changes everything", "Profit first thinking", "Small business, big margins"]),
            ("Builder Mindset", 1, "Psychology of building. Tone: steady encouragement.",
             ["Ship small, ship often", "Boring consistency wins", "Feedback is fuel", "Quit the plan, not the goal"]),
        ),
    },
    "relationships": {
        "name": "Love & Relationships",
        "emoji": "💞",
        "tagline": "Dating, connection, communication — the human stuff.",
        "accent": "#ec4899",
        "brand": {
            "niche": "modern love and human connection — dating, communication, boundaries and keeping relationships alive",
            "voice": "warm, wise, a little witty; honest about hard parts; hopeful about people",
            "audience": "adults navigating dating, partnerships and friendships in the modern world",
            "visual_style": "intimate candid photography, holding hands, shared meals, soft window light, genuine laughter, warm tones, no text in image",
        },
        "categories": _cats(
            ("Communication Keys", 2, "Talking so it lands. Tone: practical warmth.",
             ["Repair beats being right", "Listening without fixing", "The soft startup", "Asking for needs out loud"]),
            ("Modern Dating", 1, "Dating in the app era. Tone: honest, funny.",
             ["Green flags worth swiping for", "The talking stage trap", "Dating burnout is real", "Choosing effort over butterflies"]),
            ("Boundaries & Self", 1, "Healthy limits and self-respect. Tone: empowering.",
             ["No is a full sentence", "Boundaries aren't walls", "Stop auditioning for love", "You teach people how to treat you"]),
            ("Lasting Love", 1, "Keeping long-term love alive. Tone: tender, real.",
             ["Small daily deposits", "Date nights that aren't dinner", "Fighting fair", "Growing together not apart"]),
        ),
    },
    "jokes": {
        "name": "Jokes & Humor",
        "emoji": "😂",
        "tagline": "One-liners, relatable fails, and daily-life comedy.",
        "accent": "#facc15",
        "brand": {
            "niche": "everyday comedy — one-liners, relatable fails and observational humor about modern life",
            "voice": "punchy setup-punchline timing; wholesome-to-sassy; laughs WITH people never at them; no offensive or edgy-for-edgy humor",
            "audience": "anyone who needs a laugh on their scroll break",
            "visual_style": "bright playful photography, exaggerated everyday moments, colorful pop backgrounds, comic timing frozen mid-action, expressive faces, no text in image",
        },
        "categories": _cats(
            ("One-Liners", 2, "Short sharp jokes that land in one breath. Tone: quick wit.",
             ["My bed and I are in a committed relationship", "Adulting is just googling everything", "Diets and other fairy tales", "My battery dies faster than my motivation"]),
            ("Relatable Fails", 1, "Everyday disasters everyone knows. Tone: self-deprecating warmth.",
             ["Walking into a room and forgetting why", "Waving at someone who wasn't waving at you", "The alarm snooze negotiation", "Saying 'you too' to the waiter"]),
            ("Adulting Jokes", 1, "Growing up is a scam comedy. Tone: mock despair.",
             ["Taxes: the boss level nobody trained us for", "Getting excited about new pillows", "Back pain from sleeping wrong", "My social plans vs my couch"]),
            ("Food Funnies", 1, "Eating, cooking and snack crimes. Tone: playful.",
             ["Cooking rice: a gamble", "The fridge check every 20 minutes", "Diet starts Monday, again", "Ordering food while food is cooking"]),
            ("Tech & Phone Humor", 1, "Our devices, our overlords. Tone: ironic.",
             ["1% battery panic mode", "Typing and deleting the same message", "My screen time report attacked me", "Wifi down: family speaks again"]),
        ),
    },
    "corporate": {
        "name": "Corporate Life",
        "emoji": "💼",
        "tagline": "Meetings that could be emails — office humor and survival.",
        "accent": "#64748b",
        "brand": {
            "niche": "corporate life comedy and survival — meetings, emails, WFH, appraisals and the 9-to-5 experience",
            "voice": "dry, deadpan office sarcasm; painfully relatable; punches at the system never at coworkers; HR-safe but honest",
            "audience": "office workers, IT folks and anyone with a standup meeting at 10am",
            "visual_style": "office-life photography, cubicles and laptops, coffee cups by keyboards, video-call fatigue faces, fluorescent lighting irony, business casual, no text in image",
        },
        "categories": _cats(
            ("Meetings & Emails", 2, "The meeting-industrial complex. Tone: deadpan.",
             ["This meeting could have been an email", "Circling back on circling back", "The 4:55pm calendar invite", "Reply-all disasters"]),
            ("WFH Life", 1, "Remote work realities. Tone: cozy sarcasm.",
             ["Camera off, pajamas on", "You're on mute, again", "Commute from bed to desk", "The doorbell during a presentation"]),
            ("Corporate Truths", 1, "The unwritten rules. Tone: knowing smirk.",
             ["'As per my last email' is a threat", "Appraisal season theatre", "Team building nobody asked for", "The salary vs inflation race"]),
            ("Monday Blues", 1, "The weekly grief cycle. Tone: mock mourning.",
             ["Sunday evening existential dread", "Monday motivation is a myth", "Friday brain by Tuesday", "Living for the long weekend"]),
            ("Escape Plans", 1, "Side hustle and resignation dreams. Tone: hopeful mischief.",
             ["My resignation letter draft folder", "Side hustle at 6am dreams", "Cafe owner fantasy during standup", "Lottery plans in the elevator"]),
        ),
    },
    "shayari": {
        "name": "Shayari & Poetry",
        "emoji": "🌹",
        "tagline": "Dil se — ishq, dard aur zindagi in Hinglish couplets.",
        "accent": "#e11d48",
        "brand": {
            "niche": "Hinglish shayari and short poetry — ishq, dard, tanhai aur zindagi, written from the heart",
            "voice": "romantic-melancholic shayari in Hinglish (Urdu-Hindi words in Roman script — dil, ishq, khwaab, tanhai); 2-4 short lines with rhythm and a soft final punch; tehzeeb and depth, never crude",
            "audience": "desi hearts who feel deeply — shayari lovers, old souls, the heartbroken and the hopeful",
            "visual_style": "moody romantic Indian aesthetics — rain on window glass, chai steam at dusk, moonlit terrace, old handwritten letters, marigold and rose petals, warm streetlight glow, no text in image",
        },
        "categories": _cats(
            ("Ishq & Mohabbat", 2, "Love in its tender first-person glory. Tone: soft, aching-sweet.",
             ["Pehli nazar ka asar", "Uski muskurahat aur meri duniya", "Chai aur tumhari yaad", "Ishq mein sab kuch maaf"]),
            ("Dard & Tanhai", 1, "Heartbreak and loneliness. Tone: melancholic, dignified.",
             ["Adhoori mohabbat ke kisse", "Raat aur tanhai ki baatein", "Jo mila hi nahi usse khona", "Muskurahat ke peeche ka dard"]),
            ("Zindagi Ke Sabak", 1, "Life philosophy in couplets. Tone: wise, seasoned.",
             ["Waqt ka phera", "Girna aur phir uthna", "Khwaabon ki keemat", "Sabr ka phal"]),
            ("Dosti Shayari", 1, "Friendship, yaari. Tone: warm, loyal.",
             ["Yaaron ke bina zindagi adhoori", "Purani dosti ki mehak", "Door hoke bhi paas", "Bina bole samajh jaana"]),
            ("Yaadein", 1, "Memories and nostalgia. Tone: bittersweet.",
             ["Bachpan ki galiyan", "Purane ghar ki khushboo", "Woh school ke din", "Yaadon ka albeli safar"]),
        ),
    },
    "wisdom": {
        "name": "Spiritual & Wisdom",
        "emoji": "🕉️",
        "tagline": "Gita, Buddha and Stoic calm for modern chaos.",
        "accent": "#d97706",
        "brand": {
            "niche": "timeless wisdom for modern life — Gita and Buddhist insight, Stoic calm, karma, letting go and inner peace",
            "voice": "serene, simple, profound; short lines that feel ancient and current at once; never preachy, always practical",
            "audience": "seekers of calm — people tired of noise, looking inward",
            "visual_style": "serene spiritual photography, sunrise over the Ganges vibes, diyas and incense smoke, temple silhouettes, lotus on still water, meditating figures at dawn, golden hour, no text in image",
        },
        "categories": _cats(
            ("Karma & Letting Go", 2, "Do your work, release the outcome. Tone: liberating calm.",
             ["Karma kiye ja, phal ki chinta mat kar", "What you release returns lighter", "Holding on is the heaviest weight", "Detachment is not indifference"]),
            ("Inner Peace", 1, "Stillness practice. Tone: gentle guide.",
             ["The mind is a monkey, breathe", "Silence is also an answer", "Peace is a practice not a place", "One mindful chai"]),
            ("Gita in Daily Life", 1, "Bhagavad Gita applied to now. Tone: timeless teacher.",
             ["Focus on the action, not the fruit", "Change is the only constant", "Your duty over your comfort", "The self beyond the noise"]),
            ("Stoic Threads", 1, "Marcus Aurelius meets Monday. Tone: grounded strength.",
             ["Control what you can, release the rest", "Obstacles as the way", "Memento mori, live today", "Anger punishes you first"]),
        ),
    },
    "movies": {
        "name": "Movies & Pop Culture",
        "emoji": "🎬",
        "tagline": "Cinema lines, facts and lists worth rewatching for.",
        "accent": "#dc2626",
        "brand": {
            "niche": "movies and pop culture — lines that hit different, behind-the-scenes facts, rankings and the psychology of great characters",
            "voice": "enthusiastic film-buff energy; spoiler-considerate; treats blockbusters and arthouse with equal love, Bollywood and Hollywood both",
            "audience": "film lovers, binge-watchers and everyone with a rewatch comfort movie",
            "visual_style": "cinematic photography, film set lights and clapboards, theater seats glow, projector beams in dark rooms, popcorn silhouettes, dramatic movie-poster lighting, no text in image",
        },
        "categories": _cats(
            ("Lines That Hit", 2, "Dialogue that lives rent-free. Tone: reverent fan.",
             ["Movie lines that raised us", "Villains who were right", "One dialogue, whole philosophy", "Endings that changed the film"]),
            ("Behind The Scenes", 1, "True production stories. Tone: wide-eyed trivia.",
             ["Improvised scenes that stayed", "Actors who almost said no", "Movies shot in secret", "Practical effects that fooled us"]),
            ("Rankings & Lists", 1, "Watchlists and debates. Tone: playful authority.",
             ["Comfort movies for bad days", "Sequels better than the original", "Underrated gems nobody saw", "Perfect movies with zero skips"]),
            ("Character Study", 1, "Psychology of icons. Tone: thoughtful analysis.",
             ["Characters who were the real victim", "Growth arcs done right", "Why we love antiheroes", "Mentors who shaped cinema"]),
        ),
    },
    "history": {
        "name": "History & Stories",
        "emoji": "🏛️",
        "tagline": "True stories that feel fake — and lessons that last.",
        "accent": "#a16207",
        "brand": {
            "niche": "history that reads like a thriller — true stories, turning points, lost worlds and people the textbooks skipped",
            "voice": "master storyteller energy; vivid, factual, cliffhanger pacing; makes centuries feel like yesterday",
            "audience": "curious minds who stop for a good story and a 'wait, that really happened?'",
            "visual_style": "epic historical atmospheres, ancient ruins at golden hour, old maps and manuscripts, candlelit studies, museum marble halls, weathered monuments, no text in image",
        },
        "categories": _cats(
            ("Feels Fake, Is True", 2, "Unbelievable true stories. Tone: dramatic reveal.",
             ["The war stopped for a football match", "Cities lost and found again", "Messages that arrived decades late", "History's strangest coincidences"]),
            ("Turning Points", 1, "Moments that changed everything. Tone: epic hinge-of-fate.",
             ["One decision that rewrote the map", "Inventions born by accident", "The day the world almost ended", "Small acts, giant consequences"]),
            ("People You Should Know", 1, "Forgotten heroes and geniuses. Tone: overdue tribute.",
             ["The genius history forgot", "Women written out of the story", "Ordinary people, extraordinary courage", "Rivals who changed each other"]),
            ("Ancient Wisdom", 1, "Old civilizations, current lessons. Tone: awed respect.",
             ["Engineering we still can't explain", "Daily life in ancient cities", "What the ancients did better", "Libraries the world lost"]),
        ),
    },
    "science": {
        "name": "Science Facts",
        "emoji": "🔬",
        "tagline": "Space, nature, and the wow of how things work.",
        "accent": "#8b5cf6",
        "brand": {
            "niche": "mind-expanding science — space, nature, the human body and the everyday physics of life, made wonder-first",
            "voice": "wide-eyed but rigorous; wonder without woo; explains like a favorite teacher",
            "audience": "curious people who stop scrolling for a good 'whoa'",
            "visual_style": "stunning nature and space photography, macro details, aurora skies, deep ocean, microscopic worlds, rich saturated color, no text in image",
        },
        "categories": _cats(
            ("Space & Cosmos", 1, "Astronomy wonders. Tone: awe.",
             ["Scale of the universe", "Time works weirdly out there", "Moons stranger than planets", "You are made of star stuff"]),
            ("Body & Brain", 2, "Human biology surprises. Tone: fascinating.",
             ["Your body's overnight repair crew", "Gut feelings are real chemistry", "Memory is a rewrite", "The blink you never notice"]),
            ("Wild Nature", 1, "Animal and plant wonders. Tone: delighted.",
             ["Octopus intelligence", "Trees talk underground", "Migration's impossible math", "Creatures that cheat death"]),
            ("Everyday Physics", 1, "Science of daily life. Tone: playful.",
             ["Why the sky is blue, really", "Microwaves and standing waves", "Why time flies when you're busy", "The physics of a perfect cup of tea"]),
        ),
    },
}


def _presets_for_db() -> list[dict]:
    """Flatten the code PRESETS into rows for the niche_presets table."""
    return [
        {"key": key, "name": p["name"], "emoji": p["emoji"], "tagline": p["tagline"],
         "accent": p["accent"],
         "brand": {k: v for k, v in p["brand"].items()},
         "categories": [dict(c) for c in p["categories"]]}
        for key, p in PRESETS.items()
    ]


def seed(force: bool = False) -> int:
    """Seed the niche_presets DB table from code (idempotent)."""
    from . import database
    return database.seed_niches(_presets_for_db(), force=force)


def preset_list() -> list[dict]:
    """Compact list for the picker UI — read from the DB table."""
    from . import database
    return [
        {"key": n["key"], "name": n["name"], "emoji": n["emoji"], "tagline": n["tagline"],
         "accent": n["accent"], "categories": len(n["categories"])}
        for n in database.list_niches()
    ]


def get_preset(key: str) -> dict | None:
    """A full niche (from the DB) shaped like the code presets."""
    from . import database
    n = database.get_niche(key)
    if not n:
        return None
    return {"key": n["key"], "name": n["name"], "emoji": n["emoji"], "tagline": n["tagline"],
            "accent": n["accent"], "brand": n["brand"], "categories": n["categories"]}


_NICHE_SYSTEM = (
    "You design an Instagram content strategy for the topic the user gives you. Produce:\n"
    "- niche: one-line positioning statement for the account\n"
    "- voice: writing voice, 15-25 words\n"
    "- audience: who it serves, 8-15 words\n"
    "- visual_style: photography direction for AI image generation, 20-35 words, ending with "
    "'no text in image'\n"
    "- accent: a fitting brand hex color like '#0ea5e9'\n"
    "- categories: exactly 5 content pillars. Each: name (2-4 words), weight (integer 1-2; give "
    "2 to the most engaging pillar), description (one line ending with 'Tone: ...'), themes "
    "(exactly 4 specific post themes, each 3-8 words)\n"
    'Respond ONLY as JSON: {"niche":"...","voice":"...","audience":"...","visual_style":"...",'
    '"accent":"#......","categories":[{"name":"...","weight":1,"description":"...",'
    '"themes":["..."]}]}'
)


def generate_niche(topic: str) -> dict:
    """AI-build a full niche (brand + categories) for ANY topic."""
    from .providers.structured import _extract_json  # reuse the tolerant parser

    text = llm.chat_json(_NICHE_SYSTEM, f"Topic: {topic}")
    data = _extract_json(text)
    cats = []
    for c in data.get("categories", []):
        name = str(c.get("name", "")).strip()
        themes = [str(t).strip() for t in c.get("themes", []) if str(t).strip()]
        if name and themes:
            cats.append({
                "name": name,
                "weight": max(1, min(2, int(c.get("weight", 1)))),
                "description": str(c.get("description", "")).strip(),
                "themes": themes,
            })
    if len(cats) < 3:
        raise ValueError("niche generation returned too few categories")
    return {
        "name": topic.strip().title()[:40],
        "accent": str(data.get("accent", "#a855f7")).strip(),
        "brand": {
            "niche": str(data.get("niche", topic)).strip(),
            "voice": str(data.get("voice", "")).strip(),
            "audience": str(data.get("audience", "")).strip(),
            "visual_style": str(data.get("visual_style", "")).strip(),
        },
        "categories": cats,
    }


def niche_to_brand(niche: dict, handle: str = "", preset_key: str = "custom") -> dict:
    """Flatten a niche's brand block into an account brand dict (keeps handle)."""
    brand = dict(niche["brand"])
    brand["handle"] = handle
    brand["accent"] = niche.get("accent", "#a855f7")
    brand["preset"] = niche.get("key", preset_key)  # which niche is active
    return brand


def default_account(handle: str) -> dict:
    """The studio a brand-new user starts with (Glitch Life preset)."""
    preset = PRESETS["glitch-life"]
    return {
        "brand": niche_to_brand(preset, handle, preset_key="glitch-life"),
        "categories": [dict(c) for c in preset["categories"]],
        "formats": dict(DEFAULT_FORMATS),
    }
