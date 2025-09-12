#!/usr/bin/env python3
"""
Sample Recruiter Comments for Testing
Various feedback scenarios for testing comment analysis
"""

# Highly positive feedback
HIGHLY_POSITIVE_FEEDBACK = """
Exceptional candidate! One of the strongest profiles I've seen this quarter. 
Currently a Principal Engineer at Google with 15 years of progressive experience.
Led the architecture redesign that improved system performance by 300%.

Incredible executive presence - articulate, confident, and strategic thinker.
Has that rare combination of deep technical expertise and business acumen.
Multiple team members from previous roles have followed them to new companies.

Cultural fit is perfect - collaborative, innovative, and values mentorship.
Already has ideas about how to improve our current architecture.
References were glowing - described as "transformational leader" and "10x engineer."

This is a must-hire. We should move quickly before they get other offers.
Recommend fast-tracking through the process and preparing competitive offer.
"""

# Positive feedback with some concerns
POSITIVE_WITH_CONCERNS = """
Strong technical candidate with solid experience at Microsoft and Amazon.
8 years of experience with distributed systems and cloud architecture.
Communicated clearly and showed good problem-solving skills during screening.

Some concerns about the job hopping - 4 companies in 6 years. When asked,
they provided reasonable explanations but still a yellow flag.
Currently an IC (individual contributor) but applying for a lead role -
would need to assess leadership readiness more carefully.

Technical skills are definitely there. Solved the coding challenge efficiently.
Seems genuinely interested in our mission and asked thoughtful questions.
Salary expectations are on the higher end of our range.

Overall positive but recommend thorough behavioral interview to assess
stability and leadership potential. Would benefit from strong onboarding.
"""

# Mixed feedback
MIXED_FEEDBACK = """
Interesting conversation with mixed impressions. The candidate has 
an impressive academic background (PhD from MIT) and deep expertise in ML.
Published several papers and has patents in the field.

However, communication was sometimes unclear - very technical, had trouble
explaining concepts in simple terms. This could be problematic for our
cross-functional team environment.

Strong individual contributor but limited team experience. When asked about
collaboration, examples were mostly academic rather than industry-focused.
Seemed uncomfortable with our fast-paced, ambiguous startup environment.

Brilliant technically but I'm concerned about practical application and
team dynamics. Might work if paired with a strong engineering manager.
Would want the team to meet them before making a decision.
"""

# Negative feedback
NEGATIVE_FEEDBACK = """
Unfortunately, I don't think this candidate is a fit for the role.
While they have 5 years of experience, it's all at the same company
in a very different tech stack than ours.

Several red flags during the call:
- Couldn't answer basic system design questions
- Became defensive when asked about technical decisions
- Badmouthed their current employer and team extensively
- Unrealistic salary expectations (50% above range)

When asked about our company, they hadn't done any research and couldn't
articulate why they wanted to work here beyond "looking for a change."
Seemed more interested in remote work policy than the actual role.

Communication style was problematic - interrupted frequently and 
dismissed feedback about our technical challenges as "simple to solve."

Recommend passing on this candidate.
"""

# Leadership-focused feedback
LEADERSHIP_FOCUSED = """
Interviewed Sarah for the Engineering Manager position. Currently a
Tech Lead at Stripe managing 12 engineers across 2 teams.

Strong leadership philosophy - believes in servant leadership and 
empowering team members. Gave specific examples of growing junior 
engineers into senior roles. One of her reports was recently promoted
to Staff Engineer.

Impressive track record of delivery - shipped 3 major products on time
while improving team velocity by 40%. Introduced several process
improvements including better sprint planning and documentation standards.

Good balance of technical depth and people skills. Still codes 20% of
the time to stay connected with the work. Team retention rate is 95%
over 3 years - well above industry average.

Only concern is that our scale is larger (would manage 25 engineers).
However, she's managed through rapid growth before and seems capable
of scaling up. Has executive presence needed for VP track.

Strongly recommend moving forward. This is senior leadership material.
"""

# Junior candidate feedback  
JUNIOR_CANDIDATE = """
Phone screen with recent bootcamp graduate applying for Junior Developer role.
Very enthusiastic and eager to learn. Completed a 6-month intensive
full-stack program and has been doing freelance projects for 3 months.

Positives:
- Great attitude and growth mindset
- Strong portfolio projects showing progression
- Passed the basic coding assessment
- Very coachable, took feedback well during the technical discussion
- Passionate about our product space

Areas for development:
- Limited production experience
- Needs mentorship on best practices and code patterns
- Would require significant onboarding investment
- Not familiar with our specific tech stack

For a junior role, this could work well if we have bandwidth for mentoring.
Shows promise and has the right attitude. With proper guidance, could
grow into a strong contributor. Salary expectations are appropriate for level.

Recommend bringing in for team interview to assess culture fit and
learning velocity.
"""

# Overqualified candidate
OVERQUALIFIED_CANDIDATE = """
Spoke with a very senior candidate - ex-CTO of a unicorn startup that
was recently acquired. 20+ years of experience, managed 200+ engineers.
Applying for a Senior Engineer role (not leadership).

Extremely impressive background:
- Built and scaled three successful companies
- Deep expertise across multiple domains
- Published author and conference speaker
- Strong network in the industry

Concerns about fit:
- Significantly overqualified for the role level
- Salary history 3x our budget
- Says they want to be an IC but may struggle without authority
- Might get bored or leave quickly for something more senior
- Could create team dynamic issues with current leadership

When pressed on why this role, they mentioned burnout from executive
roles and wanting to "just code again." While understandable, I'm
skeptical about long-term fit. Might be better suited for a Principal
or Distinguished Engineer role if we had one.

Tough call - incredible talent but probably not the right fit for this
specific position.
"""

# Culture fit focused
CULTURE_FIT_FOCUSED = """
Great cultural fit assessment call with the candidate. Currently at a
similar-stage startup so understands our environment well.

Really resonated with our values:
- Showed strong ownership mentality with examples of going above and beyond
- Collaborative approach - talked about "we" not "I" when describing wins
- Customer-focused - has actually used our product and had suggestions
- Transparency - was very open about failures and learnings

Work style aligns well with our team:
- Comfortable with ambiguity and changing priorities
- Prefers flat organizations and direct communication
- Values speed over perfection when appropriate
- Enjoys wearing multiple hats

Technical skills are solid if not exceptional. But the cultural alignment
is so strong that I think they'd be successful here. Sometimes attitude
and fit matter more than pure technical ability.

The team would love this person. Recommend bringing them in to meet
everyone. This feels like someone who could be here for the long haul.
"""


def get_all_feedback_samples():
    """Return all sample feedback as a dictionary"""
    return {
        "highly_positive": HIGHLY_POSITIVE_FEEDBACK,
        "positive_with_concerns": POSITIVE_WITH_CONCERNS,
        "mixed": MIXED_FEEDBACK,
        "negative": NEGATIVE_FEEDBACK,
        "leadership_focused": LEADERSHIP_FOCUSED,
        "junior": JUNIOR_CANDIDATE,
        "overqualified": OVERQUALIFIED_CANDIDATE,
        "culture_fit": CULTURE_FIT_FOCUSED
    }


def get_feedback_by_sentiment(sentiment: str):
    """Get sample feedback by sentiment type"""
    samples = get_all_feedback_samples()
    sentiment_map = {
        "positive": ["highly_positive", "leadership_focused", "culture_fit"],
        "negative": ["negative"],
        "mixed": ["mixed", "positive_with_concerns", "overqualified"],
        "junior": ["junior"]
    }
    
    matching = sentiment_map.get(sentiment.lower(), [])
    if matching:
        return samples.get(matching[0], "")
    return samples.get("mixed", "")