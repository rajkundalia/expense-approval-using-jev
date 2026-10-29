# Jev J3 + J4 — Evidence quality experiment

Status: **complete**. This report analyzes retained records only. No unobserved predictions are filled in.

## Objective, source verification and scope

Compare A: J2 alone, B: J2+J3 Noul, C: J2+J4 Score, and D: J2+both. Extra judgments can request clarification/review, not verify a real claim or automatically deny it. No financial eligibility, budget enforcement, OCR, FastAPI, authentication or approval workflow is implemented.

Historical J2 verified from saved actual records: **84/87 primary agreement**, with 3 disagreements: [('J2-30', 1, 'SUPPORTED'), ('J2-30', 2, 'SUPPORTED'), ('J2-30', 3, 'SUPPORTED')]. Historical J2 Choice was not rerun; the saved 96 actual responses are retained as the development baseline.

Frozen at `2026-10-29T14:56:22.638866+00:00`, specification SHA-256 `14a3fb5ce720fb84841e6dd41aad3974ca9af511643d9511a9ca7381bf09b184`. Exact J2 policies are copied from its preregistration. Historical result SHA-256: `1159f5f746f975be3246fc394bb7333afff93597ad3208f3a70bcdf6545f6a9c`; preregistration SHA-256: `3043c85c1673151af1bebebc98a9a371001e94f7fd0abcfc4210124ac3fc2aee`.

SDK 0.7.5, Python 3.12.14, model `typesafe/jev-1.14-20261014`, gateway `https://openrouter.ai/api`. Three trials per case. 32 development cases (29 primary + 3 J1 probes), and 20 genuinely new held-out primary cases. Planned new inference requests: 96 development signal requests + 60 held-out signal requests + 60 held-out J2 requests = **216**. No historical results were changed.

## Actual SDK Score representation and question independence

The installed Score constructor takes an ordered sequence of descriptions. The three entries define levels 0, 1 and 2. ScoreAnswer exposes a numeric `score` (which can be fractional), confidence, probabilities and a legend keyed by integer level in Python; JSON keys are strings. Score is documented as a probability-weighted position, not an exact integer. Raw values are preserved without rounding, normalization or pretending discrete model output. The following region rules are offline interpretation only.

```json
{
  "j3": "LOW: p < 0.3; AMBIGUOUS: 0.3 <= p < 0.7; HIGH: p >= 0.7. Qualitative development hypotheses, not calibrated correctness or exact expected probabilities.",
  "j4": "Conceptual nearest-anchor regions: [0,0.5) -> 0, [0.5,1.5) -> 1, [1.5,2] -> 2. Raw fractional score is always retained; region assignment is Python analysis, not an SDK integer output."
}
```

J4 measures whether purpose can be assessed, not whether it qualifies. An explicit ordinary commute, entertainment purpose, or product-purpose contradiction can score near 2. J3 asks whether qualifying purpose is established for the actual purchase. Neither judgment receives another answer, expected annotation, budget or amount. Each sees only invoice_item_description, policy_category and employee_justification plus its applicable policy. Shared state/model means outputs are not statistically independent.

Official docs support mixing question types in one request. J3/J4 use one such request with separately specified instructions. Held-out J2 uses its original frozen question in a separate request; no J2 result enters the signal request. Live gateway support and actual error coverage are established by the user's run, not assumed from the offline constructor checks.

```json
{
  "Score": "(*, type: Literal['score'] = 'score', instructions: Optional[Content] = None, criteria: Annotated[collections.abc.Sequence[Content], MinLen(min_length=1)]) -> None",
  "Noul": "(*, type: Literal['noul'] = 'noul', instructions: Optional[Content] = None, criteria: typesafe_sdk._core.question_types.NoulCriteria | None = None) -> None",
  "system_one": "(self, state: Content, questions: collections.abc.Mapping[str, typesafe_sdk._core.question_types.Noul | typesafe_sdk._core.question_types.Choice | typesafe_sdk._core.question_types.Score | typesafe_sdk._core.question_types.Box | typesafe_sdk._core.question_types.NoulModel | typesafe_sdk._core.question_types.ChoiceModel | typesafe_sdk._core.question_types.ScoreModel | typesafe_sdk._core.question_types.BoxModel], *, model: str | None = None, assets: collections.abc.Mapping[str, typesafe_sdk._core.assets.Image] | None = None, retry: typesafe_sdk._core.retry.RetryPolicy | None = None, timeout: float | httpx2.Timeout | None = None, extra_headers: collections.abc.Mapping[str, str] | None = None, extra_body: collections.abc.Mapping[str, typing.Optional[JSONValue]] | None = None, response_model: type[~ResponseT] | None = None) -> Union[typesafe_sdk._core.response_types.SystemOneResponse, ~ResponseT]"
}
```

## Exact final propositions and Score question

```json
{
  "WELLNESS": {
    "essential_purpose": {
      "type": "noul",
      "instructions": {
        "applicable_policy_category": "WELLNESS",
        "applicable_policy": "The purchase must support the employee's own personal fitness or wellbeing. Potentially eligible purchases include running and sports shoes; gym or exercise clothing and equipment; fitness trackers and Garmin fitness wearables; AirPods, headphones and other workout audio accessories; gym memberships and personal training; non-medical meditation and mental-wellness subscriptions; and other identifiable products/services reasonably supporting personal fitness or wellbeing. The invoice identifies the purchase; the employee's explanation establishes claimed purpose. AirPods and similar audio accessories are candidate Wellness products by identity even if the invoice does not mention exercise. Running shoes for daily running and AirPods for gym workouts qualify. AirPods for watching movies at home do not qualify. General fashion, gaming, entertainment and arbitrary relaxation subscriptions do not automatically qualify. Casual sneakers for marathon training can present a debatable mismatch; assess conservatively rather than assume impossible use. Do not infer eligibility or ineligibility from gender-labelled product sizing. Do not calculate allowance, final reimbursement or medical eligibility.",
        "task": "Evaluate the affirmative proposition from the original evidence and applicable fixed policy. Explicitly established means reasonably understandable from the employee's words, not lengthy or formal terminology. Do not fill in missing purpose from the product, a colleague's attendance, or an event location. Bind the explanation to the identified purchase without redoing J1 category classification. This tests provided evidence, not employee truthfulness. Do not demand external proof, infer gender from sizing, calculate amounts, or use any other question's answer.",
        "proposition": "The explanation explicitly establishes the employee's own fitness or wellbeing purpose for the invoiced purchase, without assuming unstated use or disregarding an explicit contradiction in the purchased service."
      }
    },
    "explanation_sufficiency": {
      "type": "score",
      "instructions": {
        "applicable_policy_category": "WELLNESS",
        "applicable_policy": "The purchase must support the employee's own personal fitness or wellbeing. Potentially eligible purchases include running and sports shoes; gym or exercise clothing and equipment; fitness trackers and Garmin fitness wearables; AirPods, headphones and other workout audio accessories; gym memberships and personal training; non-medical meditation and mental-wellness subscriptions; and other identifiable products/services reasonably supporting personal fitness or wellbeing. The invoice identifies the purchase; the employee's explanation establishes claimed purpose. AirPods and similar audio accessories are candidate Wellness products by identity even if the invoice does not mention exercise. Running shoes for daily running and AirPods for gym workouts qualify. AirPods for watching movies at home do not qualify. General fashion, gaming, entertainment and arbitrary relaxation subscriptions do not automatically qualify. Casual sneakers for marathon training can present a debatable mismatch; assess conservatively rather than assume impossible use. Do not infer eligibility or ineligibility from gender-labelled product sizing. Do not calculate allowance, final reimbursement or medical eligibility.",
        "question": "How sufficiently informative is the employee explanation to assess its stated purpose under the applicable policy? Use the three ordered descriptions below. Measure purpose-information sufficiency, not policy eligibility, reimbursement correctness, fraud, honesty, writing quality, explanation length, or another judgment's accuracy. An explicitly excluded purpose or identifiable item-purpose contradiction can be sufficiently informative. A brief own-phone-use or home-connectivity explanation can suffice without a business-use requirement. Do not invent missing facts, require external documents, or use another question's answer."
      },
      "criteria": [
        "No usable purpose information. The explanation does not meaningfully identify why this item/service was purchased, such as 'Needed it'. Do not infer a reason from product identity alone.",
        "Partial purpose information. Relevant context is supplied but an essential purpose detail remains unresolved, such as an event with colleagues whose business purpose is not established.",
        "Sufficient purpose information. The explanation identifies its purpose clearly enough to assess it under the applicable policy, whether qualifying, excluded or materially inconsistent with the invoice. Concise explanations can suffice. Ordinary daily commuting is sufficiently clear even though excluded."
      ]
    }
  },
  "SMARTPHONE": {
    "essential_purpose": {
      "type": "noul",
      "instructions": {
        "applicable_policy_category": "SMARTPHONE",
        "applicable_policy": "Covers smartphone handsets, not tablets, laptops, watches, accessories or mobile service charges. For an identified smartphone purchase, a straightforward explanation of purchasing a phone for the employee's own use is sufficient unless contrary facts are provided. Short explanations can suffice. Do not invent professional-use requirements. Do not evaluate the amount or allowance.",
        "task": "Evaluate the affirmative proposition from the original evidence and applicable fixed policy. Explicitly established means reasonably understandable from the employee's words, not lengthy or formal terminology. Do not fill in missing purpose from the product, a colleague's attendance, or an event location. Bind the explanation to the identified purchase without redoing J1 category classification. This tests provided evidence, not employee truthfulness. Do not demand external proof, infer gender from sizing, calculate amounts, or use any other question's answer.",
        "proposition": "The explanation explicitly establishes purchase of this smartphone for the employee's own use, without contrary facts or an invented professional-use requirement."
      }
    },
    "explanation_sufficiency": {
      "type": "score",
      "instructions": {
        "applicable_policy_category": "SMARTPHONE",
        "applicable_policy": "Covers smartphone handsets, not tablets, laptops, watches, accessories or mobile service charges. For an identified smartphone purchase, a straightforward explanation of purchasing a phone for the employee's own use is sufficient unless contrary facts are provided. Short explanations can suffice. Do not invent professional-use requirements. Do not evaluate the amount or allowance.",
        "question": "How sufficiently informative is the employee explanation to assess its stated purpose under the applicable policy? Use the three ordered descriptions below. Measure purpose-information sufficiency, not policy eligibility, reimbursement correctness, fraud, honesty, writing quality, explanation length, or another judgment's accuracy. An explicitly excluded purpose or identifiable item-purpose contradiction can be sufficiently informative. A brief own-phone-use or home-connectivity explanation can suffice without a business-use requirement. Do not invent missing facts, require external documents, or use another question's answer."
      },
      "criteria": [
        "No usable purpose information. The explanation does not meaningfully identify why this item/service was purchased, such as 'Needed it'. Do not infer a reason from product identity alone.",
        "Partial purpose information. Relevant context is supplied but an essential purpose detail remains unresolved, such as an event with colleagues whose business purpose is not established.",
        "Sufficient purpose information. The explanation identifies its purpose clearly enough to assess it under the applicable policy, whether qualifying, excluded or materially inconsistent with the invoice. Concise explanations can suffice. Ordinary daily commuting is sufficiently clear even though excluded."
      ]
    }
  },
  "BROADBAND": {
    "essential_purpose": {
      "type": "noul",
      "instructions": {
        "applicable_policy_category": "BROADBAND",
        "applicable_policy": "Covers home broadband/fiber internet service, not mobile hotspots, dongles or cellular service. A reasonable explanation identifying home internet connectivity is sufficient. Do not invent a requirement for proof of hours worked from home or professional use. Do not evaluate the amount or allowance.",
        "task": "Evaluate the affirmative proposition from the original evidence and applicable fixed policy. Explicitly established means reasonably understandable from the employee's words, not lengthy or formal terminology. Do not fill in missing purpose from the product, a colleague's attendance, or an event location. Bind the explanation to the identified purchase without redoing J1 category classification. This tests provided evidence, not employee truthfulness. Do not demand external proof, infer gender from sizing, calculate amounts, or use any other question's answer.",
        "proposition": "The explanation explicitly establishes home fixed-internet connectivity as the purpose of this service, without requiring professional use or proof of hours worked at home."
      }
    },
    "explanation_sufficiency": {
      "type": "score",
      "instructions": {
        "applicable_policy_category": "BROADBAND",
        "applicable_policy": "Covers home broadband/fiber internet service, not mobile hotspots, dongles or cellular service. A reasonable explanation identifying home internet connectivity is sufficient. Do not invent a requirement for proof of hours worked from home or professional use. Do not evaluate the amount or allowance.",
        "question": "How sufficiently informative is the employee explanation to assess its stated purpose under the applicable policy? Use the three ordered descriptions below. Measure purpose-information sufficiency, not policy eligibility, reimbursement correctness, fraud, honesty, writing quality, explanation length, or another judgment's accuracy. An explicitly excluded purpose or identifiable item-purpose contradiction can be sufficiently informative. A brief own-phone-use or home-connectivity explanation can suffice without a business-use requirement. Do not invent missing facts, require external documents, or use another question's answer."
      },
      "criteria": [
        "No usable purpose information. The explanation does not meaningfully identify why this item/service was purchased, such as 'Needed it'. Do not infer a reason from product identity alone.",
        "Partial purpose information. Relevant context is supplied but an essential purpose detail remains unresolved, such as an event with colleagues whose business purpose is not established.",
        "Sufficient purpose information. The explanation identifies its purpose clearly enough to assess it under the applicable policy, whether qualifying, excluded or materially inconsistent with the invoice. Concise explanations can suffice. Ordinary daily commuting is sufficiently clear even though excluded."
      ]
    }
  },
  "MOBILE_BILL": {
    "essential_purpose": {
      "type": "noul",
      "instructions": {
        "applicable_policy_category": "MOBILE_BILL",
        "applicable_policy": "Covers prepaid and postpaid cellular voice/data service. A mobile plan including Netflix at no separately stated charge can qualify as a mobile plan. A separately charged entertainment subscription is excluded. Do not calculate or split charges. Do not invent a professional-use requirement or evaluate the amount or allowance.",
        "task": "Evaluate the affirmative proposition from the original evidence and applicable fixed policy. Explicitly established means reasonably understandable from the employee's words, not lengthy or formal terminology. Do not fill in missing purpose from the product, a colleague's attendance, or an event location. Bind the explanation to the identified purchase without redoing J1 category classification. This tests provided evidence, not employee truthfulness. Do not demand external proof, infer gender from sizing, calculate amounts, or use any other question's answer.",
        "proposition": "The explanation explicitly establishes cellular voice or mobile-data use for this service; a complimentary included streaming benefit does not negate it, while a separate entertainment subscription does not establish cellular use."
      }
    },
    "explanation_sufficiency": {
      "type": "score",
      "instructions": {
        "applicable_policy_category": "MOBILE_BILL",
        "applicable_policy": "Covers prepaid and postpaid cellular voice/data service. A mobile plan including Netflix at no separately stated charge can qualify as a mobile plan. A separately charged entertainment subscription is excluded. Do not calculate or split charges. Do not invent a professional-use requirement or evaluate the amount or allowance.",
        "question": "How sufficiently informative is the employee explanation to assess its stated purpose under the applicable policy? Use the three ordered descriptions below. Measure purpose-information sufficiency, not policy eligibility, reimbursement correctness, fraud, honesty, writing quality, explanation length, or another judgment's accuracy. An explicitly excluded purpose or identifiable item-purpose contradiction can be sufficiently informative. A brief own-phone-use or home-connectivity explanation can suffice without a business-use requirement. Do not invent missing facts, require external documents, or use another question's answer."
      },
      "criteria": [
        "No usable purpose information. The explanation does not meaningfully identify why this item/service was purchased, such as 'Needed it'. Do not infer a reason from product identity alone.",
        "Partial purpose information. Relevant context is supplied but an essential purpose detail remains unresolved, such as an event with colleagues whose business purpose is not established.",
        "Sufficient purpose information. The explanation identifies its purpose clearly enough to assess it under the applicable policy, whether qualifying, excluded or materially inconsistent with the invoice. Concise explanations can suffice. Ordinary daily commuting is sufficiently clear even though excluded."
      ]
    }
  },
  "BUSINESS_HOTEL": {
    "essential_purpose": {
      "type": "noul",
      "instructions": {
        "applicable_policy_category": "BUSINESS_HOTEL",
        "applicable_policy": "Qualifying purposes include client visits, internal company training, workshops, business offsites and other adequately explained work-related travel requiring temporary accommodation. The employee's explanation is sufficient evidence for assessing the claimed purpose in this experiment. Do not demand external client verification, meeting invitations, employer approval documents or proof beyond the explanation. Personal vacations are non-qualifying. An overnight stay alone does not establish business purpose. No fixed reimbursement cap; do not calculate amounts.",
        "task": "Evaluate the affirmative proposition from the original evidence and applicable fixed policy. Explicitly established means reasonably understandable from the employee's words, not lengthy or formal terminology. Do not fill in missing purpose from the product, a colleague's attendance, or an event location. Bind the explanation to the identified purchase without redoing J1 category classification. This tests provided evidence, not employee truthfulness. Do not demand external proof, infer gender from sizing, calculate amounts, or use any other question's answer.",
        "proposition": "The explanation explicitly establishes work-related travel requiring this temporary accommodation, such as client visits, internal training, workshops or offsites, without assuming business purpose from location or an overnight stay alone."
      }
    },
    "explanation_sufficiency": {
      "type": "score",
      "instructions": {
        "applicable_policy_category": "BUSINESS_HOTEL",
        "applicable_policy": "Qualifying purposes include client visits, internal company training, workshops, business offsites and other adequately explained work-related travel requiring temporary accommodation. The employee's explanation is sufficient evidence for assessing the claimed purpose in this experiment. Do not demand external client verification, meeting invitations, employer approval documents or proof beyond the explanation. Personal vacations are non-qualifying. An overnight stay alone does not establish business purpose. No fixed reimbursement cap; do not calculate amounts.",
        "question": "How sufficiently informative is the employee explanation to assess its stated purpose under the applicable policy? Use the three ordered descriptions below. Measure purpose-information sufficiency, not policy eligibility, reimbursement correctness, fraud, honesty, writing quality, explanation length, or another judgment's accuracy. An explicitly excluded purpose or identifiable item-purpose contradiction can be sufficiently informative. A brief own-phone-use or home-connectivity explanation can suffice without a business-use requirement. Do not invent missing facts, require external documents, or use another question's answer."
      },
      "criteria": [
        "No usable purpose information. The explanation does not meaningfully identify why this item/service was purchased, such as 'Needed it'. Do not infer a reason from product identity alone.",
        "Partial purpose information. Relevant context is supplied but an essential purpose detail remains unresolved, such as an event with colleagues whose business purpose is not established.",
        "Sufficient purpose information. The explanation identifies its purpose clearly enough to assess it under the applicable policy, whether qualifying, excluded or materially inconsistent with the invoice. Concise explanations can suffice. Ordinary daily commuting is sufficiently clear even though excluded."
      ]
    }
  },
  "BUSINESS_TRANSPORT": {
    "essential_purpose": {
      "type": "noul",
      "instructions": {
        "applicable_policy_category": "BUSINESS_TRANSPORT",
        "applicable_policy": "Qualifying purposes include travel to client meetings, business trips, transporting clients, internal business events requiring travel, and exceptional travel from home to the usual office for a specific client meeting or similarly identifiable business requirement. Ordinary daily commuting from home to the regular office is excluded. A specific work-related explanation is sufficient without external verification. Do not infer a business purpose from the transport invoice alone. No fixed reimbursement cap; do not calculate amounts.",
        "task": "Evaluate the affirmative proposition from the original evidence and applicable fixed policy. Explicitly established means reasonably understandable from the employee's words, not lengthy or formal terminology. Do not fill in missing purpose from the product, a colleague's attendance, or an event location. Bind the explanation to the identified purchase without redoing J1 category classification. This tests provided evidence, not employee truthfulness. Do not demand external proof, infer gender from sizing, calculate amounts, or use any other question's answer.",
        "proposition": "The explanation explicitly establishes a specific work-related purpose for this journey, including exceptional travel for an identifiable business requirement; ordinary daily commuting and colleague attendance alone do not establish that purpose."
      }
    },
    "explanation_sufficiency": {
      "type": "score",
      "instructions": {
        "applicable_policy_category": "BUSINESS_TRANSPORT",
        "applicable_policy": "Qualifying purposes include travel to client meetings, business trips, transporting clients, internal business events requiring travel, and exceptional travel from home to the usual office for a specific client meeting or similarly identifiable business requirement. Ordinary daily commuting from home to the regular office is excluded. A specific work-related explanation is sufficient without external verification. Do not infer a business purpose from the transport invoice alone. No fixed reimbursement cap; do not calculate amounts.",
        "question": "How sufficiently informative is the employee explanation to assess its stated purpose under the applicable policy? Use the three ordered descriptions below. Measure purpose-information sufficiency, not policy eligibility, reimbursement correctness, fraud, honesty, writing quality, explanation length, or another judgment's accuracy. An explicitly excluded purpose or identifiable item-purpose contradiction can be sufficiently informative. A brief own-phone-use or home-connectivity explanation can suffice without a business-use requirement. Do not invent missing facts, require external documents, or use another question's answer."
      },
      "criteria": [
        "No usable purpose information. The explanation does not meaningfully identify why this item/service was purchased, such as 'Needed it'. Do not infer a reason from product identity alone.",
        "Partial purpose information. Relevant context is supplied but an essential purpose detail remains unresolved, such as an event with colleagues whose business purpose is not established.",
        "Sufficient purpose information. The explanation identifies its purpose clearly enough to assess it under the applicable policy, whether qualifying, excluded or materially inconsistent with the invoice. Concise explanations can suffice. Ordinary daily commuting is sufficiently clear even though excluded."
      ]
    }
  }
}
```

Exact held-out J2 question objects are retained under `j2_questions` in preregistered.json and every raw J2 request; they match the historical frozen question objects byte-for-value after JSON decoding.

## Frozen expected annotations and original input states

### development

| ID | Group | Policy | Invoice description | Explanation | Expected J2 | Expected J3 | Expected J4 | J3/J4 rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| J2-01 | primary | WELLNESS | Nike Pegasus 41 running shoes | For my daily running. | SUPPORTED | HIGH | 2 | Own daily running is explicitly stated and sufficiently clear. |
| J2-02 | primary | WELLNESS | Adjustable dumbbell pair, 5-20 kg, home exercise equipment | For my strength-training sessions at home. | SUPPORTED | HIGH | 2 | Own strength training is explicitly stated. |
| J2-03 | primary | WELLNESS | Garmin Forerunner 265 fitness watch | To monitor my marathon training and recovery. | SUPPORTED | HIGH | 2 | Marathon training and recovery are explicit. |
| J2-04 | primary | WELLNESS | Apple AirPods Pro 2 wireless earbuds | For music during my gym workouts. | SUPPORTED | HIGH | 2 | Own gym workout purpose is explicit. |
| J2-05 | primary | WELLNESS | Apple AirPods Pro 2 wireless earbuds | For watching movies at home. | UNRELATED | LOW | 2 | Movie entertainment is explicitly excluded but clearly explained. |
| J2-06 | primary | WELLNESS | Apple AirPods Pro 2 wireless earbuds | Personal use. | UNCLEAR | LOW | 1 | Own/personal context is given but fitness or wellbeing purpose is missing. |
| J2-07 | j1_boundary_probe | WELLNESS | Converse Chuck Taylor All Star canvas high-top sneakers | For my marathon training. | UNCLEAR | AMBIGUOUS | 2 | Training purpose is clear but casual-shoe suitability is debatable; J1 boundary probe. |
| J2-08 | j1_boundary_probe | WELLNESS | Formal leather office dress shoes | For my marathon training. | INCONSISTENT | AMBIGUOUS | 2 | Training purpose is clear but dress-shoe identity conflicts; J1 diagnostic, not a primary claim. |
| J2-09 | primary | WELLNESS | Generic athletic sneakers | For my daily running. | SUPPORTED | HIGH | 2 | Own daily running is explicit; do not invent a technical-shoe requirement. |
| J2-10 | primary | WELLNESS | Headspace non-medical meditation and mental-wellness subscription | For daily guided meditation to manage stress and support my mental wellbeing. | SUPPORTED | HIGH | 2 | Own meditation and mental-wellbeing purpose is explicit. |
| J2-11 | primary | WELLNESS | Headspace non-medical meditation and mental-wellness subscription | I wanted to try it. | UNCLEAR | LOW | 0 | Wanting to try it does not identify a meaningful purpose. |
| J2-12 | primary | WELLNESS | Women's Nike Dri-FIT training leggings, size M | For my own strength-training sessions. | SUPPORTED | HIGH | 2 | Own strength training is explicit; gender-labelled sizing is irrelevant. |
| J2-13 | primary | SMARTPHONE | Apple iPhone 16 smartphone handset | Replacing my old phone for my own everyday use. | SUPPORTED | HIGH | 2 | Own everyday smartphone use is enough under policy. |
| J2-14 | primary | SMARTPHONE | Samsung Galaxy S25 smartphone handset | My new phone. | SUPPORTED | HIGH | 2 | My new phone is brief but sufficient under own-use policy. |
| J2-15 | primary | BROADBAND | Airtel Xstream Fiber home broadband monthly internet service | For internet connectivity at my home for my household. | SUPPORTED | HIGH | 2 | Home household internet connectivity suffices without work proof. |
| J2-16 | primary | MOBILE_BILL | Jio postpaid cellular voice and mobile data monthly service | For calls and mobile data on my phone. | SUPPORTED | HIGH | 2 | Own cellular calls/data use explicitly matches policy. |
| J2-17 | primary | MOBILE_BILL | Airtel postpaid cellular plan; Netflix included at no separately stated charge | For my cellular calls and mobile internet; Netflix is a complimentary included benefit. | SUPPORTED | HIGH | 2 | Cellular purpose is explicit and complimentary entertainment does not negate it. |
| J2-18 | j1_boundary_probe | MOBILE_BILL | Netflix Standard monthly subscription, separately charged mobile-account add-on | For watching films and series at home. | UNRELATED | LOW | 2 | Separate entertainment is excluded but clearly described; J1 boundary probe. |
| J2-19 | primary | BUSINESS_HOTEL | Marriott Hotel temporary accommodation, two nights | Stayed overnight while visiting our client in Bengaluru. | SUPPORTED | HIGH | 2 | Client travel explains the accommodation. |
| J2-20 | primary | BUSINESS_HOTEL | Lemon Tree Hotel temporary accommodation, one night | Overnight stay to attend internal company training in Pune. | SUPPORTED | HIGH | 2 | Internal company training explains the accommodation. |
| J2-21 | primary | BUSINESS_HOTEL | Hotel conference-property guest room, two nights | Stayed for our company's two-day planning workshop and offsite. | SUPPORTED | HIGH | 2 | Company workshop/offsite explains the stay. |
| J2-22 | primary | BUSINESS_HOTEL | Marriott Hotel temporary accommodation, three nights | Family holiday. | UNRELATED | LOW | 2 | Family vacation is excluded but sufficient to assess purpose. |
| J2-23 | primary | BUSINESS_HOTEL | Marriott Hotel temporary accommodation, one night | Stayed overnight in Bengaluru. | UNCLEAR | LOW | 1 | Location and overnight context do not establish a business purpose. |
| J2-24 | primary | BUSINESS_TRANSPORT | Uber passenger cab journey | Travelled to a client meeting at their office. | SUPPORTED | HIGH | 2 | Specific client meeting is sufficient without external verification. |
| J2-25 | primary | BUSINESS_TRANSPORT | IndiGo passenger flight from Delhi to Bengaluru | Travel to our Bengaluru branch for an internal company training event. | SUPPORTED | HIGH | 2 | Branch training event explicitly establishes business travel. |
| J2-26 | primary | BUSINESS_TRANSPORT | Uber passenger cab journey | I accompanied our client from the airport to our office for the project kickoff. | SUPPORTED | HIGH | 2 | Transporting a client for project kickoff establishes business purpose. |
| J2-27 | primary | BUSINESS_TRANSPORT | Uber passenger cab journey from home to regular office | My normal daily commute to the office. | UNRELATED | LOW | 2 | Ordinary daily commuting is excluded but explicitly established. |
| J2-28 | primary | BUSINESS_TRANSPORT | Uber passenger cab journey from home to regular office | An exceptional trip to the office specifically for a meeting with our visiting client. | SUPPORTED | HIGH | 2 | Exceptional travel for a specific visiting-client meeting is explicit. |
| J2-29 | primary | BUSINESS_TRANSPORT | Uber passenger cab journey | Had something important to attend. | UNCLEAR | LOW | 0 | Something important provides no usable purpose detail. |
| J2-30 | primary | BUSINESS_TRANSPORT | Ola passenger cab journey | Went to an event with people from my office. | UNCLEAR | AMBIGUOUS | 1 | Colleague attendance leaves business versus social purpose unresolved; avoid assuming work. |
| J2-31 | primary | WELLNESS | Gym membership: in-person gym-floor access only; no classes or app access included | I bought this for guided meditation classes in its included phone app. | INCONSISTENT | LOW | 2 | Purpose is clear but claimed app/classes contradict the actual service terms. |
| J2-32 | primary | BUSINESS_HOTEL | Marriott Hotel guest-room accommodation, one night | This purchase was the return train fare to a client meeting, not an overnight room. | INCONSISTENT | LOW | 2 | Work travel is clear but explanation explicitly denies the invoiced accommodation identity. |

### heldout

| ID | Group | Policy | Invoice description | Explanation | Expected J2 | Expected J3 | Expected J4 | J3/J4 rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EQ-H01 | primary | BUSINESS_TRANSPORT | Taxi passenger fare to a staff picnic | I chose the optional weekend staff outing purely to socialise on my day off, not for any work task. | UNRELATED | LOW | 2 | Excluded personal purpose is clear and sufficiently informative. |
| EQ-H02 | primary | BUSINESS_TRANSPORT | Passenger seat on shuttle bus to industrial training centre | To attend company safety training at our plant before operating the new equipment. | SUPPORTED | HIGH | 2 | Training purpose is explicit without requiring external evidence. |
| EQ-H03 | primary | BUSINESS_TRANSPORT | Evening taxi passenger journey to a restaurant | A networking dinner with colleagues to meet a few people; no particular business requirement was established. | UNCLEAR | AMBIGUOUS | 1 | Relevant event context lacks an essential work-purpose detail. |
| EQ-H04 | primary | BUSINESS_TRANSPORT | Airport express passenger rail ticket | Travel to staff our product demonstration booth for prospective customers at the trade exhibition. | SUPPORTED | HIGH | 2 | Business role and travel purpose are explicit. |
| EQ-H05 | primary | BUSINESS_HOTEL | Serviced-apartment temporary accommodation, two nights | Stayed locally for our internal technical workshop on the new database deployment. | SUPPORTED | HIGH | 2 | Clearly identified work event suffices without external invitations. |
| EQ-H06 | primary | WELLNESS | Indoor rowing exercise machine | For decorative display in my games room; I do not use it for exercise or wellbeing. | UNRELATED | LOW | 2 | Purpose is explicit and assessable although excluded. |
| EQ-H07 | primary | WELLNESS | Sony over-ear wireless headphones | I bought these exclusively for gaming and films at home. I use them every evening for dialogue and game sound, keep them beside the television, and never take them to exercise or use them for a wellbeing activity. | UNRELATED | LOW | 2 | Length is irrelevant; excluded purpose is sufficiently clear. |
| EQ-H08 | primary | WELLNESS | Non-slip yoga exercise mat | For my yoga. | SUPPORTED | HIGH | 2 | Few words can explicitly establish a qualifying purpose. |
| EQ-H09 | primary | SMARTPHONE | Google Pixel smartphone handset | For me. | SUPPORTED | HIGH | 2 | Own-use meaning is reasonably understood from concise wording and invoice identity. |
| EQ-H10 | primary | BROADBAND | ACT residential fixed fiber internet connection service | Connect my flat to the internet. | SUPPORTED | HIGH | 2 | Home-service purpose is clearly stated. |
| EQ-H11 | primary | MOBILE_BILL | Cellular voice and mobile data international roaming add-on | Keep my phone connected for calls and mobile internet while visiting relatives abroad. | SUPPORTED | HIGH | 2 | Cellular own-use is explicit despite personal travel context. |
| EQ-H12 | primary | MOBILE_BILL | Prepaid cellular mobile data recharge | Needed it. | UNCLEAR | LOW | 0 | No usable purpose is identified; product identity cannot supply missing explanation. |
| EQ-H13 | primary | WELLNESS | Bose QuietComfort wireless headphones | A gift for my friend to use during their workouts, not for my own use. | UNRELATED | LOW | 2 | Ownership/use exclusion is clearly assessable. |
| EQ-H14 | primary | WELLNESS | Online live Pilates class subscription; video sessions only, no exercise equipment included | This purchase bought me the exercise bike that I ride at home for fitness. | INCONSISTENT | LOW | 2 | Purpose is explicit, but does not establish qualifying use of the actual invoiced service. |
| EQ-H15 | primary | BUSINESS_HOTEL | Airport capsule-hotel overnight room | Stayed during a layover before flying out for my holiday. | UNRELATED | LOW | 2 | Excluded purpose is clear enough to assess. |
| EQ-H16 | primary | BUSINESS_TRANSPORT | Metered taxi passenger fare | Meetup. | UNCLEAR | AMBIGUOUS | 1 | Some purpose context is given but work relevance is unresolved. |
| EQ-H17 | primary | BUSINESS_HOTEL | Guesthouse overnight accommodation | A two-day gathering. | UNCLEAR | AMBIGUOUS | 1 | Event context lacks essential business-purpose detail. |
| EQ-H18 | primary | BUSINESS_TRANSPORT | Auto-rickshaw passenger trip from home to usual office | Called in exceptionally to restore the office network during an outage; this was not my normal commute. | SUPPORTED | HIGH | 2 | Identifiable business requirement and exceptional purpose are explicit. |
| EQ-H19 | primary | WELLNESS | Group personal-training exercise sessions | For improving my own strength and mobility. | SUPPORTED | HIGH | 2 | Own fitness information is explicit without medical or writing-quality judgments. |
| EQ-H20 | primary | WELLNESS | Shokz OpenRun bone-conduction sports headphones | For audio coaching during my runs, although I also listen to podcasts when relaxing. | SUPPORTED | HIGH | 2 | Qualifying purpose is explicit; an additional leisure use does not erase it. |

All historical J2 input fields, group membership and hypotheses were copied unchanged. New J3 support regions are qualitative hypotheses, not exact expected probabilities or correctness guarantees. Held-out cases add staff social outings, networking dinners, a customer exhibition, international roaming, a gift, a video-service/equipment contradiction, exceptional outage travel and mixed audio use. Their labels were fixed before inference.

## Routing rules and development-only selection

```json
[
  {
    "name": "balanced",
    "noul_min": 0.8,
    "score_min": 1.5
  },
  {
    "name": "lenient",
    "noul_min": 0.7,
    "score_min": 1.25
  },
  {
    "name": "cautious",
    "noul_min": 0.9,
    "score_min": 1.75
  }
]
```

After all development signal requests and before any held-out request, compare exactly the three registered candidate pairs using configuration D on primary development cases only. Minimize lexicographically: distinct false-CONTINUE cases, distinct unnecessary-hold cases, false-CONTINUE trials, unnecessary-hold trials, then registered candidate order (balanced first). No held-out predictions or hypotheses enter selection. Freeze the selected pair and comparison in routing_rule.json before held-out inference. If development primary paired coverage is incomplete, freeze the predeclared balanced fallback with an explicit limitation. Apply the same selected Noul/Score thresholds to B/C/D; do not tune them again.

Routing source: [routing_analysis.py](routing_analysis.py), function `route`. A never changes the original J2 semantic outcome. UNRELATED routes to EXCLUDED_PURPOSE, INCONSISTENT to REVIEW, UNCLEAR to CLARIFY. Only a J2 SUPPORTED result can CONTINUE. B requires Noul >= selected threshold; a value <0.3 goes to REVIEW, other sub-threshold values to CLARIFY. C requires raw Score >= selected threshold, otherwise CLARIFY. D applies both gates. Failures/uncollected signals are API_FAILURE/NOT_MEASURED for required gates, never a semantic label. A high Score or Noul never overrides UNRELATED or INCONSISTENT. These are experimental routing labels, not payment decisions.

```json
{
  "rule": {
    "name": "balanced",
    "noul_min": 0.8,
    "score_min": 1.5
  },
  "basis": "development-primary-only selection",
  "candidate_comparison": [
    {
      "rule": {
        "name": "balanced",
        "noul_min": 0.8,
        "score_min": 1.5
      },
      "D_development_primary": {
        "planned_trials": 87,
        "evaluable_trials": 87,
        "j2_false_supported": 3,
        "false_continue_trials": 0,
        "false_continue_cases": [],
        "unnecessary_hold_trials": 0,
        "unnecessary_hold_cases": [],
        "incremental_unnecessary_holds": 0,
        "wrong_excluded_purpose_routes": 0,
        "route_counts": {
          "CONTINUE": 57,
          "EXCLUDED_PURPOSE": 9,
          "CLARIFY": 12,
          "REVIEW": 9,
          "API_FAILURE": 0,
          "NOT_MEASURED": 0
        }
      },
      "loss": [
        0,
        0,
        0,
        0,
        0
      ],
      "all_configurations": {
        "A": {
          "planned_trials": 87,
          "evaluable_trials": 87,
          "j2_false_supported": 3,
          "false_continue_trials": 3,
          "false_continue_cases": [
            "J2-30"
          ],
          "unnecessary_hold_trials": 0,
          "unnecessary_hold_cases": [],
          "incremental_unnecessary_holds": 0,
          "wrong_excluded_purpose_routes": 0,
          "route_counts": {
            "CONTINUE": 60,
            "EXCLUDED_PURPOSE": 9,
            "CLARIFY": 12,
            "REVIEW": 6,
            "API_FAILURE": 0,
            "NOT_MEASURED": 0
          }
        },
        "B": {
          "planned_trials": 87,
          "evaluable_trials": 87,
          "j2_false_supported": 3,
          "false_continue_trials": 0,
          "false_continue_cases": [],
          "unnecessary_hold_trials": 0,
          "unnecessary_hold_cases": [],
          "incremental_unnecessary_holds": 0,
          "wrong_excluded_purpose_routes": 0,
          "route_counts": {
            "CONTINUE": 57,
            "EXCLUDED_PURPOSE": 9,
            "CLARIFY": 12,
            "REVIEW": 9,
            "API_FAILURE": 0,
            "NOT_MEASURED": 0
          }
        },
        "C": {
          "planned_trials": 87,
          "evaluable_trials": 87,
          "j2_false_supported": 3,
          "false_continue_trials": 0,
          "false_continue_cases": [],
          "unnecessary_hold_trials": 0,
          "unnecessary_hold_cases": [],
          "incremental_unnecessary_holds": 0,
          "wrong_excluded_purpose_routes": 0,
          "route_counts": {
            "CONTINUE": 57,
            "EXCLUDED_PURPOSE": 9,
            "CLARIFY": 15,
            "REVIEW": 6,
            "API_FAILURE": 0,
            "NOT_MEASURED": 0
          }
        },
        "D": {
          "planned_trials": 87,
          "evaluable_trials": 87,
          "j2_false_supported": 3,
          "false_continue_trials": 0,
          "false_continue_cases": [],
          "unnecessary_hold_trials": 0,
          "unnecessary_hold_cases": [],
          "incremental_unnecessary_holds": 0,
          "wrong_excluded_purpose_routes": 0,
          "route_counts": {
            "CONTINUE": 57,
            "EXCLUDED_PURPOSE": 9,
            "CLARIFY": 12,
            "REVIEW": 9,
            "API_FAILURE": 0,
            "NOT_MEASURED": 0
          }
        }
      }
    },
    {
      "rule": {
        "name": "lenient",
        "noul_min": 0.7,
        "score_min": 1.25
      },
      "D_development_primary": {
        "planned_trials": 87,
        "evaluable_trials": 87,
        "j2_false_supported": 3,
        "false_continue_trials": 0,
        "false_continue_cases": [],
        "unnecessary_hold_trials": 0,
        "unnecessary_hold_cases": [],
        "incremental_unnecessary_holds": 0,
        "wrong_excluded_purpose_routes": 0,
        "route_counts": {
          "CONTINUE": 57,
          "EXCLUDED_PURPOSE": 9,
          "CLARIFY": 12,
          "REVIEW": 9,
          "API_FAILURE": 0,
          "NOT_MEASURED": 0
        }
      },
      "loss": [
        0,
        0,
        0,
        0,
        1
      ],
      "all_configurations": {
        "A": {
          "planned_trials": 87,
          "evaluable_trials": 87,
          "j2_false_supported": 3,
          "false_continue_trials": 3,
          "false_continue_cases": [
            "J2-30"
          ],
          "unnecessary_hold_trials": 0,
          "unnecessary_hold_cases": [],
          "incremental_unnecessary_holds": 0,
          "wrong_excluded_purpose_routes": 0,
          "route_counts": {
            "CONTINUE": 60,
            "EXCLUDED_PURPOSE": 9,
            "CLARIFY": 12,
            "REVIEW": 6,
            "API_FAILURE": 0,
            "NOT_MEASURED": 0
          }
        },
        "B": {
          "planned_trials": 87,
          "evaluable_trials": 87,
          "j2_false_supported": 3,
          "false_continue_trials": 0,
          "false_continue_cases": [],
          "unnecessary_hold_trials": 0,
          "unnecessary_hold_cases": [],
          "incremental_unnecessary_holds": 0,
          "wrong_excluded_purpose_routes": 0,
          "route_counts": {
            "CONTINUE": 57,
            "EXCLUDED_PURPOSE": 9,
            "CLARIFY": 12,
            "REVIEW": 9,
            "API_FAILURE": 0,
            "NOT_MEASURED": 0
          }
        },
        "C": {
          "planned_trials": 87,
          "evaluable_trials": 87,
          "j2_false_supported": 3,
          "false_continue_trials": 0,
          "false_continue_cases": [],
          "unnecessary_hold_trials": 0,
          "unnecessary_hold_cases": [],
          "incremental_unnecessary_holds": 0,
          "wrong_excluded_purpose_routes": 0,
          "route_counts": {
            "CONTINUE": 57,
            "EXCLUDED_PURPOSE": 9,
            "CLARIFY": 15,
            "REVIEW": 6,
            "API_FAILURE": 0,
            "NOT_MEASURED": 0
          }
        },
        "D": {
          "planned_trials": 87,
          "evaluable_trials": 87,
          "j2_false_supported": 3,
          "false_continue_trials": 0,
          "false_continue_cases": [],
          "unnecessary_hold_trials": 0,
          "unnecessary_hold_cases": [],
          "incremental_unnecessary_holds": 0,
          "wrong_excluded_purpose_routes": 0,
          "route_counts": {
            "CONTINUE": 57,
            "EXCLUDED_PURPOSE": 9,
            "CLARIFY": 12,
            "REVIEW": 9,
            "API_FAILURE": 0,
            "NOT_MEASURED": 0
          }
        }
      }
    },
    {
      "rule": {
        "name": "cautious",
        "noul_min": 0.9,
        "score_min": 1.75
      },
      "D_development_primary": {
        "planned_trials": 87,
        "evaluable_trials": 87,
        "j2_false_supported": 3,
        "false_continue_trials": 0,
        "false_continue_cases": [],
        "unnecessary_hold_trials": 3,
        "unnecessary_hold_cases": [
          "J2-14"
        ],
        "incremental_unnecessary_holds": 3,
        "wrong_excluded_purpose_routes": 0,
        "route_counts": {
          "CONTINUE": 54,
          "EXCLUDED_PURPOSE": 9,
          "CLARIFY": 15,
          "REVIEW": 9,
          "API_FAILURE": 0,
          "NOT_MEASURED": 0
        }
      },
      "loss": [
        0,
        1,
        0,
        3,
        2
      ],
      "all_configurations": {
        "A": {
          "planned_trials": 87,
          "evaluable_trials": 87,
          "j2_false_supported": 3,
          "false_continue_trials": 3,
          "false_continue_cases": [
            "J2-30"
          ],
          "unnecessary_hold_trials": 0,
          "unnecessary_hold_cases": [],
          "incremental_unnecessary_holds": 0,
          "wrong_excluded_purpose_routes": 0,
          "route_counts": {
            "CONTINUE": 60,
            "EXCLUDED_PURPOSE": 9,
            "CLARIFY": 12,
            "REVIEW": 6,
            "API_FAILURE": 0,
            "NOT_MEASURED": 0
          }
        },
        "B": {
          "planned_trials": 87,
          "evaluable_trials": 87,
          "j2_false_supported": 3,
          "false_continue_trials": 0,
          "false_continue_cases": [],
          "unnecessary_hold_trials": 3,
          "unnecessary_hold_cases": [
            "J2-14"
          ],
          "incremental_unnecessary_holds": 3,
          "wrong_excluded_purpose_routes": 0,
          "route_counts": {
            "CONTINUE": 54,
            "EXCLUDED_PURPOSE": 9,
            "CLARIFY": 15,
            "REVIEW": 9,
            "API_FAILURE": 0,
            "NOT_MEASURED": 0
          }
        },
        "C": {
          "planned_trials": 87,
          "evaluable_trials": 87,
          "j2_false_supported": 3,
          "false_continue_trials": 0,
          "false_continue_cases": [],
          "unnecessary_hold_trials": 3,
          "unnecessary_hold_cases": [
            "J2-14"
          ],
          "incremental_unnecessary_holds": 3,
          "wrong_excluded_purpose_routes": 0,
          "route_counts": {
            "CONTINUE": 54,
            "EXCLUDED_PURPOSE": 9,
            "CLARIFY": 18,
            "REVIEW": 6,
            "API_FAILURE": 0,
            "NOT_MEASURED": 0
          }
        },
        "D": {
          "planned_trials": 87,
          "evaluable_trials": 87,
          "j2_false_supported": 3,
          "false_continue_trials": 0,
          "false_continue_cases": [],
          "unnecessary_hold_trials": 3,
          "unnecessary_hold_cases": [
            "J2-14"
          ],
          "incremental_unnecessary_holds": 3,
          "wrong_excluded_purpose_routes": 0,
          "route_counts": {
            "CONTINUE": 54,
            "EXCLUDED_PURPOSE": 9,
            "CLARIFY": 15,
            "REVIEW": 9,
            "API_FAILURE": 0,
            "NOT_MEASURED": 0
          }
        }
      }
    }
  ],
  "selection_input_scope": "development primary only; no held-out results or annotations consulted",
  "frozen_at": "2026-10-29T15:42:49.661666+00:00",
  "specification_sha256": "14a3fb5ce720fb84841e6dd41aad3974ca9af511643d9511a9ca7381bf09b184"
}
```

## Development and held-out comparisons

### development: primary

| Config | Planned | Evaluable | J2 false SUPPORTED | False CONTINUE | False CONTINUE cases | Unnecessary holds | Hold cases | Clarify | Review | API failure | Not measured |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 87 | 87 | 3 | 3 | ['J2-30'] | 0 | [] | 12 | 6 | 0 | 0 |
| B | 87 | 87 | 3 | 0 | [] | 0 | [] | 12 | 9 | 0 | 0 |
| C | 87 | 87 | 3 | 0 | [] | 0 | [] | 15 | 6 | 0 | 0 |
| D | 87 | 87 | 3 | 0 | [] | 0 | [] | 12 | 9 | 0 | 0 |

Common fully evaluable trial pairs (all four configurations available) prevent calling missing supplemental outputs an improvement. Do not subtract error-driven missing outcomes from baseline errors.

Qualitative J3 and conceptual J4 hypothesis checks (agreement with regions, not calibrated correctness):

```json
{
  "j3_region_measured": 87,
  "j3_region_agreement": 84,
  "j4_region_measured": 87,
  "j4_region_agreement": 83,
  "clear_excluded_purpose_low_noul_high_sufficiency_trials": 9,
  "clear_excluded_contrast_cases": [
    "J2-05",
    "J2-22",
    "J2-27"
  ]
}
```

The excluded-purpose contrast tests whether low qualifying evidence and high information sufficiency coexist. Such a contrast shows distinct measured semantics, but does not by itself justify another routing gate.

```json
{
  "common_evaluable_trials": 87,
  "common_configuration_summaries": {
    "A": {
      "planned_trials": 87,
      "evaluable_trials": 87,
      "j2_false_supported": 3,
      "false_continue_trials": 3,
      "false_continue_cases": [
        "J2-30"
      ],
      "unnecessary_hold_trials": 0,
      "unnecessary_hold_cases": [],
      "incremental_unnecessary_holds": 0,
      "wrong_excluded_purpose_routes": 0,
      "route_counts": {
        "CONTINUE": 60,
        "EXCLUDED_PURPOSE": 9,
        "CLARIFY": 12,
        "REVIEW": 6,
        "API_FAILURE": 0,
        "NOT_MEASURED": 0
      }
    },
    "B": {
      "planned_trials": 87,
      "evaluable_trials": 87,
      "j2_false_supported": 3,
      "false_continue_trials": 0,
      "false_continue_cases": [],
      "unnecessary_hold_trials": 0,
      "unnecessary_hold_cases": [],
      "incremental_unnecessary_holds": 0,
      "wrong_excluded_purpose_routes": 0,
      "route_counts": {
        "CONTINUE": 57,
        "EXCLUDED_PURPOSE": 9,
        "CLARIFY": 12,
        "REVIEW": 9,
        "API_FAILURE": 0,
        "NOT_MEASURED": 0
      }
    },
    "C": {
      "planned_trials": 87,
      "evaluable_trials": 87,
      "j2_false_supported": 3,
      "false_continue_trials": 0,
      "false_continue_cases": [],
      "unnecessary_hold_trials": 0,
      "unnecessary_hold_cases": [],
      "incremental_unnecessary_holds": 0,
      "wrong_excluded_purpose_routes": 0,
      "route_counts": {
        "CONTINUE": 57,
        "EXCLUDED_PURPOSE": 9,
        "CLARIFY": 15,
        "REVIEW": 6,
        "API_FAILURE": 0,
        "NOT_MEASURED": 0
      }
    },
    "D": {
      "planned_trials": 87,
      "evaluable_trials": 87,
      "j2_false_supported": 3,
      "false_continue_trials": 0,
      "false_continue_cases": [],
      "unnecessary_hold_trials": 0,
      "unnecessary_hold_cases": [],
      "incremental_unnecessary_holds": 0,
      "wrong_excluded_purpose_routes": 0,
      "route_counts": {
        "CONTINUE": 57,
        "EXCLUDED_PURPOSE": 9,
        "CLARIFY": 12,
        "REVIEW": 9,
        "API_FAILURE": 0,
        "NOT_MEASURED": 0
      }
    }
  },
  "counts": {
    "noul_catches_false_support": 3,
    "score_catches_false_support": 3,
    "score_adds_beyond_noul": 0,
    "score_extra_legitimate_hold_beyond_noul": 0,
    "both_hold_same_false_support": 3,
    "both_allow_same_false_support": 0,
    "same_B_C_D_route": 57
  },
  "cases": {
    "noul_catches_false_support": [
      "J2-30"
    ],
    "score_catches_false_support": [
      "J2-30"
    ],
    "score_adds_beyond_noul": [],
    "score_extra_legitimate_hold_beyond_noul": [],
    "both_hold_same_false_support": [
      "J2-30"
    ],
    "both_allow_same_false_support": [],
    "same_B_C_D_route": [
      "J2-01",
      "J2-02",
      "J2-03",
      "J2-04",
      "J2-09",
      "J2-10",
      "J2-12",
      "J2-13",
      "J2-14",
      "J2-15",
      "J2-16",
      "J2-17",
      "J2-19",
      "J2-20",
      "J2-21",
      "J2-24",
      "J2-25",
      "J2-26",
      "J2-28"
    ]
  },
  "details": [
    {
      "case_id": "J2-01",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-01",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-01",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-02",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-02",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-02",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-03",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-03",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-03",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-04",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-04",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-04",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-09",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-09",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-09",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-10",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-10",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-10",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-12",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-12",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-12",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-13",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-13",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-13",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-14",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-14",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-14",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-15",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-15",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-15",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-16",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-16",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-16",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-17",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-17",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-17",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-19",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-19",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-19",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-20",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-20",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-20",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-21",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-21",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-21",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-24",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-24",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-24",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-25",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-25",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-25",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-26",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-26",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-26",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-28",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-28",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-28",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "J2-30",
      "trial": 1,
      "noul_catches_false_support": true,
      "score_catches_false_support": true,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": true,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": false
    },
    {
      "case_id": "J2-30",
      "trial": 2,
      "noul_catches_false_support": true,
      "score_catches_false_support": true,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": true,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": false
    },
    {
      "case_id": "J2-30",
      "trial": 3,
      "noul_catches_false_support": true,
      "score_catches_false_support": true,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": true,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": false
    }
  ]
}
```

| Case | Trial | Expected J2 | Actual J2 | Noul | Raw Score | A | B | C | D |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| J2-01 | 1 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-01 | 2 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-01 | 3 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-02 | 1 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-02 | 2 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-02 | 3 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-03 | 1 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-03 | 2 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-03 | 3 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-04 | 1 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-04 | 2 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-04 | 3 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-05 | 1 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| J2-05 | 2 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| J2-05 | 3 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| J2-06 | 1 | UNCLEAR | UNCLEAR | 0.03 | 0.45 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-06 | 2 | UNCLEAR | UNCLEAR | 0.03 | 0.5 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-06 | 3 | UNCLEAR | UNCLEAR | 0.03 | 0.5 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-09 | 1 | SUPPORTED | SUPPORTED | 0.97 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-09 | 2 | SUPPORTED | SUPPORTED | 0.97 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-09 | 3 | SUPPORTED | SUPPORTED | 0.97 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-10 | 1 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-10 | 2 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-10 | 3 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-11 | 1 | UNCLEAR | UNCLEAR | 0.12 | 0.35 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-11 | 2 | UNCLEAR | UNCLEAR | 0.16 | 0.45 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-11 | 3 | UNCLEAR | UNCLEAR | 0.14 | 0.39 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-12 | 1 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-12 | 2 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-12 | 3 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-13 | 1 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-13 | 2 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-13 | 3 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-14 | 1 | SUPPORTED | SUPPORTED | 0.85 | 1.7 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-14 | 2 | SUPPORTED | SUPPORTED | 0.85 | 1.65 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-14 | 3 | SUPPORTED | SUPPORTED | 0.84 | 1.72 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-15 | 1 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-15 | 2 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-15 | 3 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-16 | 1 | SUPPORTED | SUPPORTED | 0.98 | 1.98 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-16 | 2 | SUPPORTED | SUPPORTED | 0.98 | 1.97 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-16 | 3 | SUPPORTED | SUPPORTED | 0.98 | 1.96 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-17 | 1 | SUPPORTED | SUPPORTED | 0.99 | 1.97 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-17 | 2 | SUPPORTED | SUPPORTED | 0.99 | 1.98 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-17 | 3 | SUPPORTED | SUPPORTED | 0.99 | 1.97 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-19 | 1 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-19 | 2 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-19 | 3 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-20 | 1 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-20 | 2 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-20 | 3 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-21 | 1 | SUPPORTED | SUPPORTED | 0.98 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-21 | 2 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-21 | 3 | SUPPORTED | SUPPORTED | 0.99 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-22 | 1 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| J2-22 | 2 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| J2-22 | 3 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| J2-23 | 1 | UNCLEAR | UNCLEAR | 0.02 | 0.26 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-23 | 2 | UNCLEAR | UNCLEAR | 0.03 | 0.31 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-23 | 3 | UNCLEAR | UNCLEAR | 0.02 | 0.25 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-24 | 1 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-24 | 2 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-24 | 3 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-25 | 1 | SUPPORTED | SUPPORTED | 0.98 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-25 | 2 | SUPPORTED | SUPPORTED | 0.98 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-25 | 3 | SUPPORTED | SUPPORTED | 0.98 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-26 | 1 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-26 | 2 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-26 | 3 | SUPPORTED | SUPPORTED | 0.99 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-27 | 1 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| J2-27 | 2 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| J2-27 | 3 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| J2-28 | 1 | SUPPORTED | SUPPORTED | 0.98 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-28 | 2 | SUPPORTED | SUPPORTED | 0.99 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-28 | 3 | SUPPORTED | SUPPORTED | 0.98 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| J2-29 | 1 | UNCLEAR | UNCLEAR | 0.03 | 0.27 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-29 | 2 | UNCLEAR | UNCLEAR | 0.03 | 0.3 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-29 | 3 | UNCLEAR | UNCLEAR | 0.03 | 0.3 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-30 | 1 | UNCLEAR | SUPPORTED | 0.22 | 1.01 | CONTINUE | REVIEW | CLARIFY | REVIEW |
| J2-30 | 2 | UNCLEAR | SUPPORTED | 0.24 | 1.02 | CONTINUE | REVIEW | CLARIFY | REVIEW |
| J2-30 | 3 | UNCLEAR | SUPPORTED | 0.21 | 1.01 | CONTINUE | REVIEW | CLARIFY | REVIEW |
| J2-31 | 1 | INCONSISTENT | INCONSISTENT | 0.08 | 2.0 | REVIEW | REVIEW | REVIEW | REVIEW |
| J2-31 | 2 | INCONSISTENT | INCONSISTENT | 0.06 | 2.0 | REVIEW | REVIEW | REVIEW | REVIEW |
| J2-31 | 3 | INCONSISTENT | INCONSISTENT | 0.08 | 2.0 | REVIEW | REVIEW | REVIEW | REVIEW |
| J2-32 | 1 | INCONSISTENT | INCONSISTENT | 0.03 | 1.99 | REVIEW | REVIEW | REVIEW | REVIEW |
| J2-32 | 2 | INCONSISTENT | INCONSISTENT | 0.03 | 1.99 | REVIEW | REVIEW | REVIEW | REVIEW |
| J2-32 | 3 | INCONSISTENT | INCONSISTENT | 0.03 | 1.99 | REVIEW | REVIEW | REVIEW | REVIEW |

### development: j1_boundary_probe

| Config | Planned | Evaluable | J2 false SUPPORTED | False CONTINUE | False CONTINUE cases | Unnecessary holds | Hold cases | Clarify | Review | API failure | Not measured |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 9 | 9 | 0 | 0 | [] | 0 | [] | 3 | 3 | 0 | 0 |
| B | 9 | 9 | 0 | 0 | [] | 0 | [] | 3 | 3 | 0 | 0 |
| C | 9 | 9 | 0 | 0 | [] | 0 | [] | 3 | 3 | 0 | 0 |
| D | 9 | 9 | 0 | 0 | [] | 0 | [] | 3 | 3 | 0 | 0 |

Common fully evaluable trial pairs (all four configurations available) prevent calling missing supplemental outputs an improvement. Do not subtract error-driven missing outcomes from baseline errors.

Qualitative J3 and conceptual J4 hypothesis checks (agreement with regions, not calibrated correctness):

```json
{
  "j3_region_measured": 9,
  "j3_region_agreement": 3,
  "j4_region_measured": 9,
  "j4_region_agreement": 9,
  "clear_excluded_purpose_low_noul_high_sufficiency_trials": 3,
  "clear_excluded_contrast_cases": [
    "J2-18"
  ]
}
```

The excluded-purpose contrast tests whether low qualifying evidence and high information sufficiency coexist. Such a contrast shows distinct measured semantics, but does not by itself justify another routing gate.

```json
{
  "common_evaluable_trials": 9,
  "common_configuration_summaries": {
    "A": {
      "planned_trials": 9,
      "evaluable_trials": 9,
      "j2_false_supported": 0,
      "false_continue_trials": 0,
      "false_continue_cases": [],
      "unnecessary_hold_trials": 0,
      "unnecessary_hold_cases": [],
      "incremental_unnecessary_holds": 0,
      "wrong_excluded_purpose_routes": 0,
      "route_counts": {
        "CONTINUE": 0,
        "EXCLUDED_PURPOSE": 3,
        "CLARIFY": 3,
        "REVIEW": 3,
        "API_FAILURE": 0,
        "NOT_MEASURED": 0
      }
    },
    "B": {
      "planned_trials": 9,
      "evaluable_trials": 9,
      "j2_false_supported": 0,
      "false_continue_trials": 0,
      "false_continue_cases": [],
      "unnecessary_hold_trials": 0,
      "unnecessary_hold_cases": [],
      "incremental_unnecessary_holds": 0,
      "wrong_excluded_purpose_routes": 0,
      "route_counts": {
        "CONTINUE": 0,
        "EXCLUDED_PURPOSE": 3,
        "CLARIFY": 3,
        "REVIEW": 3,
        "API_FAILURE": 0,
        "NOT_MEASURED": 0
      }
    },
    "C": {
      "planned_trials": 9,
      "evaluable_trials": 9,
      "j2_false_supported": 0,
      "false_continue_trials": 0,
      "false_continue_cases": [],
      "unnecessary_hold_trials": 0,
      "unnecessary_hold_cases": [],
      "incremental_unnecessary_holds": 0,
      "wrong_excluded_purpose_routes": 0,
      "route_counts": {
        "CONTINUE": 0,
        "EXCLUDED_PURPOSE": 3,
        "CLARIFY": 3,
        "REVIEW": 3,
        "API_FAILURE": 0,
        "NOT_MEASURED": 0
      }
    },
    "D": {
      "planned_trials": 9,
      "evaluable_trials": 9,
      "j2_false_supported": 0,
      "false_continue_trials": 0,
      "false_continue_cases": [],
      "unnecessary_hold_trials": 0,
      "unnecessary_hold_cases": [],
      "incremental_unnecessary_holds": 0,
      "wrong_excluded_purpose_routes": 0,
      "route_counts": {
        "CONTINUE": 0,
        "EXCLUDED_PURPOSE": 3,
        "CLARIFY": 3,
        "REVIEW": 3,
        "API_FAILURE": 0,
        "NOT_MEASURED": 0
      }
    }
  },
  "counts": {
    "noul_catches_false_support": 0,
    "score_catches_false_support": 0,
    "score_adds_beyond_noul": 0,
    "score_extra_legitimate_hold_beyond_noul": 0,
    "both_hold_same_false_support": 0,
    "both_allow_same_false_support": 0,
    "same_B_C_D_route": 0
  },
  "cases": {
    "noul_catches_false_support": [],
    "score_catches_false_support": [],
    "score_adds_beyond_noul": [],
    "score_extra_legitimate_hold_beyond_noul": [],
    "both_hold_same_false_support": [],
    "both_allow_same_false_support": [],
    "same_B_C_D_route": []
  },
  "details": []
}
```

| Case | Trial | Expected J2 | Actual J2 | Noul | Raw Score | A | B | C | D |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| J2-07 | 1 | UNCLEAR | UNCLEAR | 0.93 | 1.99 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-07 | 2 | UNCLEAR | UNCLEAR | 0.93 | 1.98 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-07 | 3 | UNCLEAR | UNCLEAR | 0.92 | 1.99 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| J2-08 | 1 | INCONSISTENT | INCONSISTENT | 0.71 | 1.97 | REVIEW | REVIEW | REVIEW | REVIEW |
| J2-08 | 2 | INCONSISTENT | INCONSISTENT | 0.75 | 1.97 | REVIEW | REVIEW | REVIEW | REVIEW |
| J2-08 | 3 | INCONSISTENT | INCONSISTENT | 0.72 | 1.97 | REVIEW | REVIEW | REVIEW | REVIEW |
| J2-18 | 1 | UNRELATED | UNRELATED | 0.02 | 1.95 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| J2-18 | 2 | UNRELATED | UNRELATED | 0.02 | 1.94 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| J2-18 | 3 | UNRELATED | UNRELATED | 0.02 | 1.95 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |

### heldout: primary

| Config | Planned | Evaluable | J2 false SUPPORTED | False CONTINUE | False CONTINUE cases | Unnecessary holds | Hold cases | Clarify | Review | API failure | Not measured |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 60 | 60 | 0 | 0 | [] | 0 | [] | 12 | 6 | 0 | 0 |
| B | 60 | 60 | 0 | 0 | [] | 0 | [] | 12 | 6 | 0 | 0 |
| C | 60 | 60 | 0 | 0 | [] | 0 | [] | 12 | 6 | 0 | 0 |
| D | 60 | 60 | 0 | 0 | [] | 0 | [] | 12 | 6 | 0 | 0 |

Common fully evaluable trial pairs (all four configurations available) prevent calling missing supplemental outputs an improvement. Do not subtract error-driven missing outcomes from baseline errors.

Qualitative J3 and conceptual J4 hypothesis checks (agreement with regions, not calibrated correctness):

```json
{
  "j3_region_measured": 60,
  "j3_region_agreement": 54,
  "j4_region_measured": 60,
  "j4_region_agreement": 60,
  "clear_excluded_purpose_low_noul_high_sufficiency_trials": 15,
  "clear_excluded_contrast_cases": [
    "EQ-H01",
    "EQ-H06",
    "EQ-H07",
    "EQ-H13",
    "EQ-H15"
  ]
}
```

The excluded-purpose contrast tests whether low qualifying evidence and high information sufficiency coexist. Such a contrast shows distinct measured semantics, but does not by itself justify another routing gate.

```json
{
  "common_evaluable_trials": 60,
  "common_configuration_summaries": {
    "A": {
      "planned_trials": 60,
      "evaluable_trials": 60,
      "j2_false_supported": 0,
      "false_continue_trials": 0,
      "false_continue_cases": [],
      "unnecessary_hold_trials": 0,
      "unnecessary_hold_cases": [],
      "incremental_unnecessary_holds": 0,
      "wrong_excluded_purpose_routes": 0,
      "route_counts": {
        "CONTINUE": 30,
        "EXCLUDED_PURPOSE": 12,
        "CLARIFY": 12,
        "REVIEW": 6,
        "API_FAILURE": 0,
        "NOT_MEASURED": 0
      }
    },
    "B": {
      "planned_trials": 60,
      "evaluable_trials": 60,
      "j2_false_supported": 0,
      "false_continue_trials": 0,
      "false_continue_cases": [],
      "unnecessary_hold_trials": 0,
      "unnecessary_hold_cases": [],
      "incremental_unnecessary_holds": 0,
      "wrong_excluded_purpose_routes": 0,
      "route_counts": {
        "CONTINUE": 30,
        "EXCLUDED_PURPOSE": 12,
        "CLARIFY": 12,
        "REVIEW": 6,
        "API_FAILURE": 0,
        "NOT_MEASURED": 0
      }
    },
    "C": {
      "planned_trials": 60,
      "evaluable_trials": 60,
      "j2_false_supported": 0,
      "false_continue_trials": 0,
      "false_continue_cases": [],
      "unnecessary_hold_trials": 0,
      "unnecessary_hold_cases": [],
      "incremental_unnecessary_holds": 0,
      "wrong_excluded_purpose_routes": 0,
      "route_counts": {
        "CONTINUE": 30,
        "EXCLUDED_PURPOSE": 12,
        "CLARIFY": 12,
        "REVIEW": 6,
        "API_FAILURE": 0,
        "NOT_MEASURED": 0
      }
    },
    "D": {
      "planned_trials": 60,
      "evaluable_trials": 60,
      "j2_false_supported": 0,
      "false_continue_trials": 0,
      "false_continue_cases": [],
      "unnecessary_hold_trials": 0,
      "unnecessary_hold_cases": [],
      "incremental_unnecessary_holds": 0,
      "wrong_excluded_purpose_routes": 0,
      "route_counts": {
        "CONTINUE": 30,
        "EXCLUDED_PURPOSE": 12,
        "CLARIFY": 12,
        "REVIEW": 6,
        "API_FAILURE": 0,
        "NOT_MEASURED": 0
      }
    }
  },
  "counts": {
    "noul_catches_false_support": 0,
    "score_catches_false_support": 0,
    "score_adds_beyond_noul": 0,
    "score_extra_legitimate_hold_beyond_noul": 0,
    "both_hold_same_false_support": 0,
    "both_allow_same_false_support": 0,
    "same_B_C_D_route": 30
  },
  "cases": {
    "noul_catches_false_support": [],
    "score_catches_false_support": [],
    "score_adds_beyond_noul": [],
    "score_extra_legitimate_hold_beyond_noul": [],
    "both_hold_same_false_support": [],
    "both_allow_same_false_support": [],
    "same_B_C_D_route": [
      "EQ-H02",
      "EQ-H04",
      "EQ-H05",
      "EQ-H08",
      "EQ-H09",
      "EQ-H10",
      "EQ-H11",
      "EQ-H18",
      "EQ-H19",
      "EQ-H20"
    ]
  },
  "details": [
    {
      "case_id": "EQ-H02",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H02",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H02",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H04",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H04",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H04",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H05",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H05",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H05",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H08",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H08",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H08",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H09",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H09",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H09",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H10",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H10",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H10",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H11",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H11",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H11",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H18",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H18",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H18",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H19",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H19",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H19",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H20",
      "trial": 1,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H20",
      "trial": 2,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    },
    {
      "case_id": "EQ-H20",
      "trial": 3,
      "noul_catches_false_support": false,
      "score_catches_false_support": false,
      "score_adds_beyond_noul": false,
      "score_extra_legitimate_hold_beyond_noul": false,
      "both_hold_same_false_support": false,
      "both_allow_same_false_support": false,
      "same_B_C_D_route": true
    }
  ]
}
```

| Case | Trial | Expected J2 | Actual J2 | Noul | Raw Score | A | B | C | D |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EQ-H01 | 1 | UNRELATED | UNRELATED | 0.01 | 1.96 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| EQ-H01 | 2 | UNRELATED | UNRELATED | 0.01 | 1.96 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| EQ-H01 | 3 | UNRELATED | UNRELATED | 0.01 | 1.96 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| EQ-H02 | 1 | SUPPORTED | SUPPORTED | 0.94 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H02 | 2 | SUPPORTED | SUPPORTED | 0.92 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H02 | 3 | SUPPORTED | SUPPORTED | 0.94 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H03 | 1 | UNCLEAR | UNCLEAR | 0.09 | 1.38 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| EQ-H03 | 2 | UNCLEAR | UNCLEAR | 0.09 | 1.38 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| EQ-H03 | 3 | UNCLEAR | UNCLEAR | 0.09 | 1.38 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| EQ-H04 | 1 | SUPPORTED | SUPPORTED | 0.97 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H04 | 2 | SUPPORTED | SUPPORTED | 0.98 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H04 | 3 | SUPPORTED | SUPPORTED | 0.97 | 2.0 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H05 | 1 | SUPPORTED | SUPPORTED | 0.97 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H05 | 2 | SUPPORTED | SUPPORTED | 0.97 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H05 | 3 | SUPPORTED | SUPPORTED | 0.97 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H06 | 1 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| EQ-H06 | 2 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| EQ-H06 | 3 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| EQ-H07 | 1 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| EQ-H07 | 2 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| EQ-H07 | 3 | UNRELATED | UNRELATED | 0.01 | 2.0 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| EQ-H08 | 1 | SUPPORTED | SUPPORTED | 0.94 | 1.95 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H08 | 2 | SUPPORTED | SUPPORTED | 0.93 | 1.94 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H08 | 3 | SUPPORTED | SUPPORTED | 0.95 | 1.96 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H09 | 1 | SUPPORTED | SUPPORTED | 0.98 | 1.95 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H09 | 2 | SUPPORTED | SUPPORTED | 0.98 | 1.96 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H09 | 3 | SUPPORTED | SUPPORTED | 0.98 | 1.95 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H10 | 1 | SUPPORTED | SUPPORTED | 0.96 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H10 | 2 | SUPPORTED | SUPPORTED | 0.96 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H10 | 3 | SUPPORTED | SUPPORTED | 0.97 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H11 | 1 | SUPPORTED | SUPPORTED | 0.97 | 1.97 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H11 | 2 | SUPPORTED | SUPPORTED | 0.97 | 1.96 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H11 | 3 | SUPPORTED | SUPPORTED | 0.97 | 1.97 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H12 | 1 | UNCLEAR | UNCLEAR | 0.09 | 0.0 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| EQ-H12 | 2 | UNCLEAR | UNCLEAR | 0.08 | 0.01 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| EQ-H12 | 3 | UNCLEAR | UNCLEAR | 0.07 | 0.0 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| EQ-H13 | 1 | UNRELATED | INCONSISTENT | 0.01 | 1.97 | REVIEW | REVIEW | REVIEW | REVIEW |
| EQ-H13 | 2 | UNRELATED | INCONSISTENT | 0.02 | 1.97 | REVIEW | REVIEW | REVIEW | REVIEW |
| EQ-H13 | 3 | UNRELATED | INCONSISTENT | 0.01 | 1.97 | REVIEW | REVIEW | REVIEW | REVIEW |
| EQ-H14 | 1 | INCONSISTENT | INCONSISTENT | 0.12 | 2.0 | REVIEW | REVIEW | REVIEW | REVIEW |
| EQ-H14 | 2 | INCONSISTENT | INCONSISTENT | 0.11 | 2.0 | REVIEW | REVIEW | REVIEW | REVIEW |
| EQ-H14 | 3 | INCONSISTENT | INCONSISTENT | 0.11 | 1.99 | REVIEW | REVIEW | REVIEW | REVIEW |
| EQ-H15 | 1 | UNRELATED | UNRELATED | 0.02 | 1.96 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| EQ-H15 | 2 | UNRELATED | UNRELATED | 0.03 | 1.96 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| EQ-H15 | 3 | UNRELATED | UNRELATED | 0.02 | 1.96 | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE | EXCLUDED_PURPOSE |
| EQ-H16 | 1 | UNCLEAR | UNCLEAR | 0.09 | 0.7 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| EQ-H16 | 2 | UNCLEAR | UNCLEAR | 0.09 | 0.61 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| EQ-H16 | 3 | UNCLEAR | UNCLEAR | 0.11 | 0.64 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| EQ-H17 | 1 | UNCLEAR | UNCLEAR | 0.42 | 1.07 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| EQ-H17 | 2 | UNCLEAR | UNCLEAR | 0.47 | 1.1 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| EQ-H17 | 3 | UNCLEAR | UNCLEAR | 0.38 | 1.07 | CLARIFY | CLARIFY | CLARIFY | CLARIFY |
| EQ-H18 | 1 | SUPPORTED | SUPPORTED | 0.96 | 1.98 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H18 | 2 | SUPPORTED | SUPPORTED | 0.95 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H18 | 3 | SUPPORTED | SUPPORTED | 0.95 | 1.98 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H19 | 1 | SUPPORTED | SUPPORTED | 0.97 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H19 | 2 | SUPPORTED | SUPPORTED | 0.97 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H19 | 3 | SUPPORTED | SUPPORTED | 0.97 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H20 | 1 | SUPPORTED | SUPPORTED | 0.97 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H20 | 2 | SUPPORTED | SUPPORTED | 0.97 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |
| EQ-H20 | 3 | SUPPORTED | SUPPORTED | 0.97 | 1.99 | CONTINUE | CONTINUE | CONTINUE | CONTINUE |

False CONTINUE means routing a J2 SUPPORTED prediction onward while its preregistered J2 hypothesis is not SUPPORTED. Unnecessary holds mean CLARIFY/REVIEW on expected-SUPPORTED cases; incremental holds count only new holds beyond A. Repeated trials are counted but distinct affected case IDs are reported. Probe results never enter primary selection or headline held-out metrics. An API error is an observed failure, not semantic UNCLEAR.

## Ambiguous office-event case J2-30

Invoice: Ola passenger cab journey. Explanation: 'Went to an event with people from my office.' Frozen J2 hypothesis: UNCLEAR. Historical J2 actually returned SUPPORTED in all three trials. This is unsupported inference of business purpose relative to the hypothesis; it does not establish what the employee really did. J3 hypothesis is AMBIGUOUS; J4 conceptual level is 1 because colleague attendance leaves work purpose unresolved.

```json
[
  {
    "case_id": "J2-30",
    "trial": 1,
    "expected_j2": "UNCLEAR",
    "expected_j3": "AMBIGUOUS",
    "expected_j4": 1,
    "j2": "SUPPORTED",
    "j3": 0.22,
    "j4": 1.01,
    "routes": {
      "A": "CONTINUE",
      "B": "REVIEW",
      "C": "CLARIFY",
      "D": "REVIEW"
    }
  },
  {
    "case_id": "J2-30",
    "trial": 2,
    "expected_j2": "UNCLEAR",
    "expected_j3": "AMBIGUOUS",
    "expected_j4": 1,
    "j2": "SUPPORTED",
    "j3": 0.24,
    "j4": 1.02,
    "routes": {
      "A": "CONTINUE",
      "B": "REVIEW",
      "C": "CLARIFY",
      "D": "REVIEW"
    }
  },
  {
    "case_id": "J2-30",
    "trial": 3,
    "expected_j2": "UNCLEAR",
    "expected_j3": "AMBIGUOUS",
    "expected_j4": 1,
    "j2": "SUPPORTED",
    "j3": 0.21,
    "j4": 1.01,
    "routes": {
      "A": "CONTINUE",
      "B": "REVIEW",
      "C": "CLARIFY",
      "D": "REVIEW"
    }
  }
]
```

Check whether a gate holds this case without holding concise legitimate phone, broadband or fitness explanations. Catching it means requesting evidence/clarification, not discovering fraud or verifying a business event. If both supplemental questions pass it, they have not repaired the known limitation. If both hold it, shared catches do not prove Score adds value beyond Noul.

## Individual responses, hypotheses and repeatability

### development: Noul and Score trials

| Case | Trial | Raw Noul | J3 region | Raw Score | J4 region | Score confidence | Score distribution | J3 status | J4 status | Request ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| J2-01 | 1 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 1225.428 |
| J2-01 | 2 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 558.425 |
| J2-01 | 3 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 598.173 |
| J2-02 | 1 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 589.919 |
| J2-02 | 2 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 586.038 |
| J2-02 | 3 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 544.925 |
| J2-03 | 1 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 595.861 |
| J2-03 | 2 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 560.949 |
| J2-03 | 3 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 645.775 |
| J2-04 | 1 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 696.435 |
| J2-04 | 2 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 620.26 |
| J2-04 | 3 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 656.334 |
| J2-05 | 1 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 596.449 |
| J2-05 | 2 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 559.372 |
| J2-05 | 3 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 569.392 |
| J2-06 | 1 | 0.03 | LOW | 0.45 | 0 | 0.31 | {'0': 0.67, '1': 0.2, '2': 0.13} | ok | ok | 588.042 |
| J2-06 | 2 | 0.03 | LOW | 0.5 | 1 | 0.27 | {'0': 0.64, '1': 0.23, '2': 0.13} | ok | ok | 570.338 |
| J2-06 | 3 | 0.03 | LOW | 0.5 | 1 | 0.25 | {'0': 0.62, '1': 0.26, '2': 0.12} | ok | ok | 693.522 |
| J2-07 | 1 | 0.93 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 575.867 |
| J2-07 | 2 | 0.93 | HIGH | 1.98 | 2 | 0.97 | {'0': 0.0, '1': 0.02, '2': 0.98} | ok | ok | 587.326 |
| J2-07 | 3 | 0.92 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 591.075 |
| J2-08 | 1 | 0.71 | HIGH | 1.97 | 2 | 0.97 | {'0': 0.0, '1': 0.02, '2': 0.98} | ok | ok | 619.968 |
| J2-08 | 2 | 0.75 | HIGH | 1.97 | 2 | 0.97 | {'0': 0.0, '1': 0.02, '2': 0.98} | ok | ok | 601.197 |
| J2-08 | 3 | 0.72 | HIGH | 1.97 | 2 | 0.97 | {'0': 0.0, '1': 0.02, '2': 0.98} | ok | ok | 636.382 |
| J2-09 | 1 | 0.97 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 608.523 |
| J2-09 | 2 | 0.97 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 583.94 |
| J2-09 | 3 | 0.97 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 576.799 |
| J2-10 | 1 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 745.686 |
| J2-10 | 2 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 564.077 |
| J2-10 | 3 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 602.376 |
| J2-11 | 1 | 0.12 | LOW | 0.35 | 0 | 0.47 | {'0': 0.76, '1': 0.13, '2': 0.11} | ok | ok | 562.318 |
| J2-11 | 2 | 0.16 | LOW | 0.45 | 0 | 0.34 | {'0': 0.7, '1': 0.16, '2': 0.14} | ok | ok | 595.698 |
| J2-11 | 3 | 0.14 | LOW | 0.39 | 0 | 0.41 | {'0': 0.74, '1': 0.13, '2': 0.13} | ok | ok | 568.155 |
| J2-12 | 1 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 560.944 |
| J2-12 | 2 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 563.414 |
| J2-12 | 3 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 587.314 |
| J2-13 | 1 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 761.054 |
| J2-13 | 2 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 563.223 |
| J2-13 | 3 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 673.64 |
| J2-14 | 1 | 0.85 | HIGH | 1.7 | 2 | 0.55 | {'0': 0.12, '1': 0.06, '2': 0.82} | ok | ok | 570.667 |
| J2-14 | 2 | 0.85 | HIGH | 1.65 | 2 | 0.49 | {'0': 0.14, '1': 0.06, '2': 0.8} | ok | ok | 587.644 |
| J2-14 | 3 | 0.84 | HIGH | 1.72 | 2 | 0.56 | {'0': 0.11, '1': 0.07, '2': 0.82} | ok | ok | 573.123 |
| J2-15 | 1 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 556.633 |
| J2-15 | 2 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 566.861 |
| J2-15 | 3 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 598.586 |
| J2-16 | 1 | 0.98 | HIGH | 1.98 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 590.782 |
| J2-16 | 2 | 0.98 | HIGH | 1.97 | 2 | 0.94 | {'0': 0.01, '1': 0.02, '2': 0.97} | ok | ok | 545.282 |
| J2-16 | 3 | 0.98 | HIGH | 1.96 | 2 | 0.94 | {'0': 0.01, '1': 0.02, '2': 0.97} | ok | ok | 571.543 |
| J2-17 | 1 | 0.99 | HIGH | 1.97 | 2 | 0.97 | {'0': 0.0, '1': 0.02, '2': 0.98} | ok | ok | 587.77 |
| J2-17 | 2 | 0.99 | HIGH | 1.98 | 2 | 0.97 | {'0': 0.0, '1': 0.02, '2': 0.98} | ok | ok | 575.096 |
| J2-17 | 3 | 0.99 | HIGH | 1.97 | 2 | 0.97 | {'0': 0.0, '1': 0.02, '2': 0.98} | ok | ok | 584.641 |
| J2-18 | 1 | 0.02 | LOW | 1.95 | 2 | 0.93 | {'0': 0.01, '1': 0.03, '2': 0.96} | ok | ok | 570.567 |
| J2-18 | 2 | 0.02 | LOW | 1.94 | 2 | 0.93 | {'0': 0.01, '1': 0.03, '2': 0.96} | ok | ok | 592.526 |
| J2-18 | 3 | 0.02 | LOW | 1.95 | 2 | 0.93 | {'0': 0.01, '1': 0.03, '2': 0.96} | ok | ok | 564.209 |
| J2-19 | 1 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 612.083 |
| J2-19 | 2 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 557.082 |
| J2-19 | 3 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 580.975 |
| J2-20 | 1 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 596.888 |
| J2-20 | 2 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 564.256 |
| J2-20 | 3 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 601.203 |
| J2-21 | 1 | 0.98 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 582.447 |
| J2-21 | 2 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 616.452 |
| J2-21 | 3 | 0.99 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 584.674 |
| J2-22 | 1 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 599.487 |
| J2-22 | 2 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 597.768 |
| J2-22 | 3 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 616.165 |
| J2-23 | 1 | 0.02 | LOW | 0.26 | 0 | 0.61 | {'0': 0.76, '1': 0.22, '2': 0.02} | ok | ok | 568.397 |
| J2-23 | 2 | 0.03 | LOW | 0.31 | 0 | 0.52 | {'0': 0.71, '1': 0.26, '2': 0.03} | ok | ok | 581.107 |
| J2-23 | 3 | 0.02 | LOW | 0.25 | 0 | 0.61 | {'0': 0.76, '1': 0.22, '2': 0.02} | ok | ok | 574.174 |
| J2-24 | 1 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 627.214 |
| J2-24 | 2 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 588.284 |
| J2-24 | 3 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 576.533 |
| J2-25 | 1 | 0.98 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 614.257 |
| J2-25 | 2 | 0.98 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 567.303 |
| J2-25 | 3 | 0.98 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 687.878 |
| J2-26 | 1 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 580.576 |
| J2-26 | 2 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 577.167 |
| J2-26 | 3 | 0.99 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 580.988 |
| J2-27 | 1 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 617.156 |
| J2-27 | 2 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 586.369 |
| J2-27 | 3 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 596.197 |
| J2-28 | 1 | 0.98 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 578.816 |
| J2-28 | 2 | 0.99 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 572.839 |
| J2-28 | 3 | 0.98 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 581.051 |
| J2-29 | 1 | 0.03 | LOW | 0.27 | 0 | 0.61 | {'0': 0.75, '1': 0.24, '2': 0.01} | ok | ok | 551.004 |
| J2-29 | 2 | 0.03 | LOW | 0.3 | 0 | 0.56 | {'0': 0.72, '1': 0.27, '2': 0.01} | ok | ok | 555.635 |
| J2-29 | 3 | 0.03 | LOW | 0.3 | 0 | 0.55 | {'0': 0.71, '1': 0.28, '2': 0.01} | ok | ok | 588.836 |
| J2-30 | 1 | 0.22 | LOW | 1.01 | 1 | 0.97 | {'0': 0.0, '1': 0.98, '2': 0.02} | ok | ok | 666.72 |
| J2-30 | 2 | 0.24 | LOW | 1.02 | 1 | 0.97 | {'0': 0.0, '1': 0.98, '2': 0.02} | ok | ok | 592.668 |
| J2-30 | 3 | 0.21 | LOW | 1.01 | 1 | 0.98 | {'0': 0.0, '1': 0.99, '2': 0.01} | ok | ok | 610.365 |
| J2-31 | 1 | 0.08 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 576.959 |
| J2-31 | 2 | 0.06 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 575.381 |
| J2-31 | 3 | 0.08 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 679.456 |
| J2-32 | 1 | 0.03 | LOW | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 559.774 |
| J2-32 | 2 | 0.03 | LOW | 1.99 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 570.738 |
| J2-32 | 3 | 0.03 | LOW | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 723.206 |

### heldout: Noul and Score trials

| Case | Trial | Raw Noul | J3 region | Raw Score | J4 region | Score confidence | Score distribution | J3 status | J4 status | Request ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EQ-H01 | 1 | 0.01 | LOW | 1.96 | 2 | 0.94 | {'0': 0.0, '1': 0.04, '2': 0.96} | ok | ok | 785.34 |
| EQ-H01 | 2 | 0.01 | LOW | 1.96 | 2 | 0.94 | {'0': 0.0, '1': 0.04, '2': 0.96} | ok | ok | 580.113 |
| EQ-H01 | 3 | 0.01 | LOW | 1.96 | 2 | 0.94 | {'0': 0.0, '1': 0.04, '2': 0.96} | ok | ok | 585.945 |
| EQ-H02 | 1 | 0.94 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 610.841 |
| EQ-H02 | 2 | 0.92 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 587.331 |
| EQ-H02 | 3 | 0.94 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 587.669 |
| EQ-H03 | 1 | 0.09 | LOW | 1.38 | 1 | 0.43 | {'0': 0.0, '1': 0.62, '2': 0.38} | ok | ok | 690.338 |
| EQ-H03 | 2 | 0.09 | LOW | 1.38 | 1 | 0.41 | {'0': 0.0, '1': 0.61, '2': 0.39} | ok | ok | 591.678 |
| EQ-H03 | 3 | 0.09 | LOW | 1.38 | 1 | 0.43 | {'0': 0.0, '1': 0.62, '2': 0.38} | ok | ok | 588.413 |
| EQ-H04 | 1 | 0.97 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 585.713 |
| EQ-H04 | 2 | 0.98 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 584.417 |
| EQ-H04 | 3 | 0.97 | HIGH | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 580.102 |
| EQ-H05 | 1 | 0.97 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 568.249 |
| EQ-H05 | 2 | 0.97 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 617.675 |
| EQ-H05 | 3 | 0.97 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 568.433 |
| EQ-H06 | 1 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 610.746 |
| EQ-H06 | 2 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 923.84 |
| EQ-H06 | 3 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 565.932 |
| EQ-H07 | 1 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 578.165 |
| EQ-H07 | 2 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 653.189 |
| EQ-H07 | 3 | 0.01 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 558.371 |
| EQ-H08 | 1 | 0.94 | HIGH | 1.95 | 2 | 0.93 | {'0': 0.01, '1': 0.03, '2': 0.96} | ok | ok | 551.773 |
| EQ-H08 | 2 | 0.93 | HIGH | 1.94 | 2 | 0.9 | {'0': 0.02, '1': 0.03, '2': 0.95} | ok | ok | 566.732 |
| EQ-H08 | 3 | 0.95 | HIGH | 1.96 | 2 | 0.94 | {'0': 0.01, '1': 0.02, '2': 0.97} | ok | ok | 564.154 |
| EQ-H09 | 1 | 0.98 | HIGH | 1.95 | 2 | 0.94 | {'0': 0.01, '1': 0.02, '2': 0.97} | ok | ok | 576.307 |
| EQ-H09 | 2 | 0.98 | HIGH | 1.96 | 2 | 0.94 | {'0': 0.01, '1': 0.02, '2': 0.97} | ok | ok | 582.84 |
| EQ-H09 | 3 | 0.98 | HIGH | 1.95 | 2 | 0.91 | {'0': 0.02, '1': 0.02, '2': 0.96} | ok | ok | 573.81 |
| EQ-H10 | 1 | 0.96 | HIGH | 1.99 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 570.321 |
| EQ-H10 | 2 | 0.96 | HIGH | 1.99 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 592.266 |
| EQ-H10 | 3 | 0.97 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 566.301 |
| EQ-H11 | 1 | 0.97 | HIGH | 1.97 | 2 | 0.97 | {'0': 0.0, '1': 0.02, '2': 0.98} | ok | ok | 565.479 |
| EQ-H11 | 2 | 0.97 | HIGH | 1.96 | 2 | 0.95 | {'0': 0.0, '1': 0.03, '2': 0.97} | ok | ok | 569.281 |
| EQ-H11 | 3 | 0.97 | HIGH | 1.97 | 2 | 0.97 | {'0': 0.0, '1': 0.02, '2': 0.98} | ok | ok | 573.794 |
| EQ-H12 | 1 | 0.09 | LOW | 0.0 | 0 | 1.0 | {'0': 1.0, '1': 0.0, '2': 0.0} | ok | ok | 596.929 |
| EQ-H12 | 2 | 0.08 | LOW | 0.01 | 0 | 1.0 | {'0': 1.0, '1': 0.0, '2': 0.0} | ok | ok | 616.847 |
| EQ-H12 | 3 | 0.07 | LOW | 0.0 | 0 | 1.0 | {'0': 1.0, '1': 0.0, '2': 0.0} | ok | ok | 551.469 |
| EQ-H13 | 1 | 0.01 | LOW | 1.97 | 2 | 0.95 | {'0': 0.0, '1': 0.03, '2': 0.97} | ok | ok | 597.562 |
| EQ-H13 | 2 | 0.02 | LOW | 1.97 | 2 | 0.95 | {'0': 0.0, '1': 0.03, '2': 0.97} | ok | ok | 558.567 |
| EQ-H13 | 3 | 0.01 | LOW | 1.97 | 2 | 0.95 | {'0': 0.0, '1': 0.03, '2': 0.97} | ok | ok | 598.014 |
| EQ-H14 | 1 | 0.12 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 606.517 |
| EQ-H14 | 2 | 0.11 | LOW | 2.0 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 573.355 |
| EQ-H14 | 3 | 0.11 | LOW | 1.99 | 2 | 1.0 | {'0': 0.0, '1': 0.0, '2': 1.0} | ok | ok | 604.476 |
| EQ-H15 | 1 | 0.02 | LOW | 1.96 | 2 | 0.95 | {'0': 0.0, '1': 0.03, '2': 0.97} | ok | ok | 564.434 |
| EQ-H15 | 2 | 0.03 | LOW | 1.96 | 2 | 0.95 | {'0': 0.0, '1': 0.03, '2': 0.97} | ok | ok | 639.686 |
| EQ-H15 | 3 | 0.02 | LOW | 1.96 | 2 | 0.95 | {'0': 0.0, '1': 0.03, '2': 0.97} | ok | ok | 567.979 |
| EQ-H16 | 1 | 0.09 | LOW | 0.7 | 1 | 0.34 | {'0': 0.37, '1': 0.56, '2': 0.07} | ok | ok | 595.773 |
| EQ-H16 | 2 | 0.09 | LOW | 0.61 | 1 | 0.27 | {'0': 0.44, '1': 0.51, '2': 0.05} | ok | ok | 659.671 |
| EQ-H16 | 3 | 0.11 | LOW | 0.64 | 1 | 0.28 | {'0': 0.42, '1': 0.52, '2': 0.06} | ok | ok | 575.309 |
| EQ-H17 | 1 | 0.42 | AMBIGUOUS | 1.07 | 1 | 0.79 | {'0': 0.03, '1': 0.86, '2': 0.11} | ok | ok | 595.658 |
| EQ-H17 | 2 | 0.47 | AMBIGUOUS | 1.1 | 1 | 0.79 | {'0': 0.02, '1': 0.86, '2': 0.12} | ok | ok | 562.814 |
| EQ-H17 | 3 | 0.38 | AMBIGUOUS | 1.07 | 1 | 0.8 | {'0': 0.03, '1': 0.87, '2': 0.1} | ok | ok | 592.118 |
| EQ-H18 | 1 | 0.96 | HIGH | 1.98 | 2 | 0.97 | {'0': 0.0, '1': 0.02, '2': 0.98} | ok | ok | 546.75 |
| EQ-H18 | 2 | 0.95 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 559.359 |
| EQ-H18 | 3 | 0.95 | HIGH | 1.98 | 2 | 0.97 | {'0': 0.0, '1': 0.02, '2': 0.98} | ok | ok | 563.767 |
| EQ-H19 | 1 | 0.97 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 551.677 |
| EQ-H19 | 2 | 0.97 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 578.915 |
| EQ-H19 | 3 | 0.97 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 597.765 |
| EQ-H20 | 1 | 0.97 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 584.8 |
| EQ-H20 | 2 | 0.97 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 596.836 |
| EQ-H20 | 3 | 0.97 | HIGH | 1.99 | 2 | 0.98 | {'0': 0.0, '1': 0.01, '2': 0.99} | ok | ok | 611.241 |

| Split | Group | Case | Config | Trial routes | All 3 routes agree |
| --- | --- | --- | --- | --- | --- |
| development | primary | J2-01 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-01 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-01 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-01 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-02 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-02 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-02 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-02 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-03 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-03 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-03 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-03 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-04 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-04 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-04 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-04 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-05 | A | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | primary | J2-05 | B | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | primary | J2-05 | C | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | primary | J2-05 | D | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | primary | J2-06 | A | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-06 | B | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-06 | C | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-06 | D | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-09 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-09 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-09 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-09 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-10 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-10 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-10 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-10 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-11 | A | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-11 | B | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-11 | C | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-11 | D | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-12 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-12 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-12 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-12 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-13 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-13 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-13 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-13 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-14 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-14 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-14 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-14 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-15 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-15 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-15 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-15 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-16 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-16 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-16 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-16 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-17 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-17 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-17 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-17 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-19 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-19 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-19 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-19 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-20 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-20 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-20 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-20 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-21 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-21 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-21 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-21 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-22 | A | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | primary | J2-22 | B | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | primary | J2-22 | C | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | primary | J2-22 | D | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | primary | J2-23 | A | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-23 | B | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-23 | C | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-23 | D | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-24 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-24 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-24 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-24 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-25 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-25 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-25 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-25 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-26 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-26 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-26 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-26 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-27 | A | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | primary | J2-27 | B | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | primary | J2-27 | C | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | primary | J2-27 | D | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | primary | J2-28 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-28 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-28 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-28 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-29 | A | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-29 | B | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-29 | C | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-29 | D | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-30 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| development | primary | J2-30 | B | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| development | primary | J2-30 | C | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | primary | J2-30 | D | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| development | primary | J2-31 | A | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| development | primary | J2-31 | B | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| development | primary | J2-31 | C | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| development | primary | J2-31 | D | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| development | primary | J2-32 | A | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| development | primary | J2-32 | B | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| development | primary | J2-32 | C | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| development | primary | J2-32 | D | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| development | j1_boundary_probe | J2-07 | A | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | j1_boundary_probe | J2-07 | B | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | j1_boundary_probe | J2-07 | C | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | j1_boundary_probe | J2-07 | D | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| development | j1_boundary_probe | J2-08 | A | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| development | j1_boundary_probe | J2-08 | B | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| development | j1_boundary_probe | J2-08 | C | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| development | j1_boundary_probe | J2-08 | D | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| development | j1_boundary_probe | J2-18 | A | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | j1_boundary_probe | J2-18 | B | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | j1_boundary_probe | J2-18 | C | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| development | j1_boundary_probe | J2-18 | D | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H01 | A | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H01 | B | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H01 | C | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H01 | D | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H02 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H02 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H02 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H02 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H03 | A | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H03 | B | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H03 | C | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H03 | D | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H04 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H04 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H04 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H04 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H05 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H05 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H05 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H05 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H06 | A | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H06 | B | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H06 | C | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H06 | D | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H07 | A | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H07 | B | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H07 | C | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H07 | D | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H08 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H08 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H08 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H08 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H09 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H09 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H09 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H09 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H10 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H10 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H10 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H10 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H11 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H11 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H11 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H11 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H12 | A | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H12 | B | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H12 | C | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H12 | D | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H13 | A | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| heldout | primary | EQ-H13 | B | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| heldout | primary | EQ-H13 | C | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| heldout | primary | EQ-H13 | D | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| heldout | primary | EQ-H14 | A | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| heldout | primary | EQ-H14 | B | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| heldout | primary | EQ-H14 | C | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| heldout | primary | EQ-H14 | D | ['REVIEW', 'REVIEW', 'REVIEW'] | True |
| heldout | primary | EQ-H15 | A | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H15 | B | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H15 | C | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H15 | D | ['EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE', 'EXCLUDED_PURPOSE'] | True |
| heldout | primary | EQ-H16 | A | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H16 | B | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H16 | C | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H16 | D | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H17 | A | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H17 | B | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H17 | C | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H17 | D | ['CLARIFY', 'CLARIFY', 'CLARIFY'] | True |
| heldout | primary | EQ-H18 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H18 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H18 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H18 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H19 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H19 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H19 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H19 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H20 | A | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H20 | B | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H20 | C | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |
| heldout | primary | EQ-H20 | D | ['CONTINUE', 'CONTINUE', 'CONTINUE'] | True |

Raw Noul/Score values and every distribution above remain separate observations, never averaged into a fabricated response. Matching routes can hide probability changes. Historical and new J2 individual Choice distributions, confidence and request timings are below.

| Baseline | Case | Trial | Choice | Confidence | Full distribution | Request ms | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| development (historical) | J2-01 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 1304.946 | ok |
| development (historical) | J2-02 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 620.671 | ok |
| development (historical) | J2-03 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 571.03 | ok |
| development (historical) | J2-04 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 591.182 | ok |
| development (historical) | J2-05 | 1 | UNRELATED | 0.99 | {'SUPPORTED': 0.0, 'UNRELATED': 0.99, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.01} | 641.334 | ok |
| development (historical) | J2-06 | 1 | UNCLEAR | 0.91 | {'SUPPORTED': 0.07, 'UNRELATED': 0.0, 'UNCLEAR': 0.93, 'INCONSISTENT': 0.0} | 594.513 | ok |
| development (historical) | J2-07 | 1 | UNCLEAR | 0.73 | {'SUPPORTED': 0.16, 'UNRELATED': 0.0, 'UNCLEAR': 0.8, 'INCONSISTENT': 0.04} | 572.862 | ok |
| development (historical) | J2-08 | 1 | INCONSISTENT | 0.75 | {'SUPPORTED': 0.03, 'UNRELATED': 0.0, 'UNCLEAR': 0.16, 'INCONSISTENT': 0.81} | 593.771 | ok |
| development (historical) | J2-09 | 1 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.0} | 586.229 | ok |
| development (historical) | J2-10 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 580.987 | ok |
| development (historical) | J2-11 | 1 | UNCLEAR | 0.41 | {'SUPPORTED': 0.44, 'UNRELATED': 0.0, 'UNCLEAR': 0.56, 'INCONSISTENT': 0.0} | 579.135 | ok |
| development (historical) | J2-12 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 584.582 | ok |
| development (historical) | J2-13 | 1 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.01, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 652.94 | ok |
| development (historical) | J2-14 | 1 | SUPPORTED | 0.97 | {'SUPPORTED': 0.98, 'UNRELATED': 0.0, 'UNCLEAR': 0.02, 'INCONSISTENT': 0.0} | 768.073 | ok |
| development (historical) | J2-15 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 576.753 | ok |
| development (historical) | J2-16 | 1 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.0} | 600.906 | ok |
| development (historical) | J2-17 | 1 | SUPPORTED | 0.97 | {'SUPPORTED': 0.98, 'UNRELATED': 0.0, 'UNCLEAR': 0.02, 'INCONSISTENT': 0.0} | 731.97 | ok |
| development (historical) | J2-18 | 1 | UNRELATED | 0.91 | {'SUPPORTED': 0.01, 'UNRELATED': 0.93, 'UNCLEAR': 0.03, 'INCONSISTENT': 0.03} | 555.178 | ok |
| development (historical) | J2-19 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 587.445 | ok |
| development (historical) | J2-20 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 572.84 | ok |
| development (historical) | J2-21 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 571.095 | ok |
| development (historical) | J2-22 | 1 | UNRELATED | 1.0 | {'SUPPORTED': 0.0, 'UNRELATED': 1.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 728.437 | ok |
| development (historical) | J2-23 | 1 | UNCLEAR | 0.97 | {'SUPPORTED': 0.02, 'UNRELATED': 0.0, 'UNCLEAR': 0.98, 'INCONSISTENT': 0.0} | 576.39 | ok |
| development (historical) | J2-24 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 560.059 | ok |
| development (historical) | J2-25 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 572.12 | ok |
| development (historical) | J2-26 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 598.805 | ok |
| development (historical) | J2-27 | 1 | UNRELATED | 1.0 | {'SUPPORTED': 0.0, 'UNRELATED': 1.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 593.666 | ok |
| development (historical) | J2-28 | 1 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.01} | 784.855 | ok |
| development (historical) | J2-29 | 1 | UNCLEAR | 0.92 | {'SUPPORTED': 0.06, 'UNRELATED': 0.0, 'UNCLEAR': 0.94, 'INCONSISTENT': 0.0} | 594.123 | ok |
| development (historical) | J2-30 | 1 | SUPPORTED | 0.43 | {'SUPPORTED': 0.57, 'UNRELATED': 0.0, 'UNCLEAR': 0.43, 'INCONSISTENT': 0.0} | 600.616 | ok |
| development (historical) | J2-31 | 1 | INCONSISTENT | 1.0 | {'SUPPORTED': 0.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 1.0} | 607.659 | ok |
| development (historical) | J2-32 | 1 | INCONSISTENT | 0.96 | {'SUPPORTED': 0.0, 'UNRELATED': 0.02, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.97} | 829.406 | ok |
| development (historical) | J2-12 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 576.35 | ok |
| development (historical) | J2-13 | 2 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.01, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 581.326 | ok |
| development (historical) | J2-14 | 2 | SUPPORTED | 0.97 | {'SUPPORTED': 0.98, 'UNRELATED': 0.0, 'UNCLEAR': 0.02, 'INCONSISTENT': 0.0} | 758.608 | ok |
| development (historical) | J2-15 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 574.225 | ok |
| development (historical) | J2-16 | 2 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.0} | 589.413 | ok |
| development (historical) | J2-17 | 2 | SUPPORTED | 0.97 | {'SUPPORTED': 0.98, 'UNRELATED': 0.0, 'UNCLEAR': 0.02, 'INCONSISTENT': 0.0} | 578.078 | ok |
| development (historical) | J2-18 | 2 | UNRELATED | 0.87 | {'SUPPORTED': 0.02, 'UNRELATED': 0.9, 'UNCLEAR': 0.04, 'INCONSISTENT': 0.04} | 574.634 | ok |
| development (historical) | J2-19 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 594.06 | ok |
| development (historical) | J2-20 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 595.574 | ok |
| development (historical) | J2-21 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 594.911 | ok |
| development (historical) | J2-22 | 2 | UNRELATED | 1.0 | {'SUPPORTED': 0.0, 'UNRELATED': 1.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 598.905 | ok |
| development (historical) | J2-23 | 2 | UNCLEAR | 0.97 | {'SUPPORTED': 0.02, 'UNRELATED': 0.0, 'UNCLEAR': 0.98, 'INCONSISTENT': 0.0} | 597.25 | ok |
| development (historical) | J2-24 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 629.234 | ok |
| development (historical) | J2-25 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 611.071 | ok |
| development (historical) | J2-26 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 584.35 | ok |
| development (historical) | J2-27 | 2 | UNRELATED | 1.0 | {'SUPPORTED': 0.0, 'UNRELATED': 1.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 574.504 | ok |
| development (historical) | J2-28 | 2 | SUPPORTED | 0.95 | {'SUPPORTED': 0.96, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.03} | 687.15 | ok |
| development (historical) | J2-29 | 2 | UNCLEAR | 0.93 | {'SUPPORTED': 0.05, 'UNRELATED': 0.0, 'UNCLEAR': 0.95, 'INCONSISTENT': 0.0} | 567.805 | ok |
| development (historical) | J2-30 | 2 | SUPPORTED | 0.35 | {'SUPPORTED': 0.51, 'UNRELATED': 0.0, 'UNCLEAR': 0.49, 'INCONSISTENT': 0.0} | 589.415 | ok |
| development (historical) | J2-31 | 2 | INCONSISTENT | 1.0 | {'SUPPORTED': 0.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 1.0} | 713.571 | ok |
| development (historical) | J2-32 | 2 | INCONSISTENT | 0.96 | {'SUPPORTED': 0.0, 'UNRELATED': 0.03, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.97} | 573.32 | ok |
| development (historical) | J2-01 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 590.067 | ok |
| development (historical) | J2-02 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 615.829 | ok |
| development (historical) | J2-03 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 576.026 | ok |
| development (historical) | J2-04 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 598.763 | ok |
| development (historical) | J2-05 | 2 | UNRELATED | 0.99 | {'SUPPORTED': 0.0, 'UNRELATED': 0.99, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.01} | 714.504 | ok |
| development (historical) | J2-06 | 2 | UNCLEAR | 0.89 | {'SUPPORTED': 0.08, 'UNRELATED': 0.0, 'UNCLEAR': 0.92, 'INCONSISTENT': 0.0} | 601.455 | ok |
| development (historical) | J2-07 | 2 | UNCLEAR | 0.71 | {'SUPPORTED': 0.17, 'UNRELATED': 0.0, 'UNCLEAR': 0.78, 'INCONSISTENT': 0.05} | 773.936 | ok |
| development (historical) | J2-08 | 2 | INCONSISTENT | 0.75 | {'SUPPORTED': 0.03, 'UNRELATED': 0.0, 'UNCLEAR': 0.16, 'INCONSISTENT': 0.81} | 573.72 | ok |
| development (historical) | J2-09 | 2 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.0} | 571.928 | ok |
| development (historical) | J2-10 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 696.47 | ok |
| development (historical) | J2-11 | 2 | UNCLEAR | 0.41 | {'SUPPORTED': 0.44, 'UNRELATED': 0.0, 'UNCLEAR': 0.56, 'INCONSISTENT': 0.0} | 599.845 | ok |
| development (historical) | J2-23 | 3 | UNCLEAR | 0.96 | {'SUPPORTED': 0.03, 'UNRELATED': 0.0, 'UNCLEAR': 0.97, 'INCONSISTENT': 0.0} | 607.419 | ok |
| development (historical) | J2-24 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 581.662 | ok |
| development (historical) | J2-25 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 569.32 | ok |
| development (historical) | J2-26 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 559.192 | ok |
| development (historical) | J2-27 | 3 | UNRELATED | 1.0 | {'SUPPORTED': 0.0, 'UNRELATED': 1.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 556.215 | ok |
| development (historical) | J2-28 | 3 | SUPPORTED | 0.97 | {'SUPPORTED': 0.98, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.02} | 580.705 | ok |
| development (historical) | J2-29 | 3 | UNCLEAR | 0.93 | {'SUPPORTED': 0.05, 'UNRELATED': 0.0, 'UNCLEAR': 0.95, 'INCONSISTENT': 0.0} | 569.904 | ok |
| development (historical) | J2-30 | 3 | SUPPORTED | 0.35 | {'SUPPORTED': 0.51, 'UNRELATED': 0.0, 'UNCLEAR': 0.49, 'INCONSISTENT': 0.0} | 627.503 | ok |
| development (historical) | J2-31 | 3 | INCONSISTENT | 0.99 | {'SUPPORTED': 0.01, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.99} | 554.344 | ok |
| development (historical) | J2-32 | 3 | INCONSISTENT | 0.96 | {'SUPPORTED': 0.0, 'UNRELATED': 0.03, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.97} | 569.745 | ok |
| development (historical) | J2-01 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 587.446 | ok |
| development (historical) | J2-02 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 735.556 | ok |
| development (historical) | J2-03 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 588.034 | ok |
| development (historical) | J2-04 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 597.037 | ok |
| development (historical) | J2-05 | 3 | UNRELATED | 0.99 | {'SUPPORTED': 0.0, 'UNRELATED': 0.99, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.01} | 578.629 | ok |
| development (historical) | J2-06 | 3 | UNCLEAR | 0.91 | {'SUPPORTED': 0.06, 'UNRELATED': 0.01, 'UNCLEAR': 0.93, 'INCONSISTENT': 0.0} | 584.997 | ok |
| development (historical) | J2-07 | 3 | UNCLEAR | 0.73 | {'SUPPORTED': 0.16, 'UNRELATED': 0.0, 'UNCLEAR': 0.8, 'INCONSISTENT': 0.04} | 596.035 | ok |
| development (historical) | J2-08 | 3 | INCONSISTENT | 0.76 | {'SUPPORTED': 0.03, 'UNRELATED': 0.0, 'UNCLEAR': 0.15, 'INCONSISTENT': 0.82} | 711.464 | ok |
| development (historical) | J2-09 | 3 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.0} | 572.052 | ok |
| development (historical) | J2-10 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 567.587 | ok |
| development (historical) | J2-11 | 3 | UNCLEAR | 0.41 | {'SUPPORTED': 0.44, 'UNRELATED': 0.0, 'UNCLEAR': 0.56, 'INCONSISTENT': 0.0} | 560.725 | ok |
| development (historical) | J2-12 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 567.498 | ok |
| development (historical) | J2-13 | 3 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.01, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 568.482 | ok |
| development (historical) | J2-14 | 3 | SUPPORTED | 0.97 | {'SUPPORTED': 0.98, 'UNRELATED': 0.0, 'UNCLEAR': 0.02, 'INCONSISTENT': 0.0} | 579.335 | ok |
| development (historical) | J2-15 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 724.123 | ok |
| development (historical) | J2-16 | 3 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.0} | 577.628 | ok |
| development (historical) | J2-17 | 3 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.0} | 548.511 | ok |
| development (historical) | J2-18 | 3 | UNRELATED | 0.88 | {'SUPPORTED': 0.01, 'UNRELATED': 0.91, 'UNCLEAR': 0.04, 'INCONSISTENT': 0.04} | 563.653 | ok |
| development (historical) | J2-19 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 564.03 | ok |
| development (historical) | J2-20 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 812.328 | ok |
| development (historical) | J2-21 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 646.164 | ok |
| development (historical) | J2-22 | 3 | UNRELATED | 1.0 | {'SUPPORTED': 0.0, 'UNRELATED': 1.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 624.807 | ok |
| heldout (new) | EQ-H01 | 1 | UNRELATED | 0.87 | {'SUPPORTED': 0.04, 'UNRELATED': 0.9, 'UNCLEAR': 0.05, 'INCONSISTENT': 0.01} | 771.747 | ok |
| heldout (new) | EQ-H02 | 1 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.0} | 580.544 | ok |
| heldout (new) | EQ-H03 | 1 | UNCLEAR | 0.56 | {'SUPPORTED': 0.18, 'UNRELATED': 0.14, 'UNCLEAR': 0.67, 'INCONSISTENT': 0.01} | 557.111 | ok |
| heldout (new) | EQ-H04 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 739.305 | ok |
| heldout (new) | EQ-H05 | 1 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.01} | 565.315 | ok |
| heldout (new) | EQ-H06 | 1 | UNRELATED | 0.95 | {'SUPPORTED': 0.0, 'UNRELATED': 0.96, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.04} | 586.553 | ok |
| heldout (new) | EQ-H07 | 1 | UNRELATED | 1.0 | {'SUPPORTED': 0.0, 'UNRELATED': 1.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 594.737 | ok |
| heldout (new) | EQ-H08 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 560.192 | ok |
| heldout (new) | EQ-H09 | 1 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.0} | 562.865 | ok |
| heldout (new) | EQ-H10 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 550.632 | ok |
| heldout (new) | EQ-H11 | 1 | SUPPORTED | 0.77 | {'SUPPORTED': 0.83, 'UNRELATED': 0.14, 'UNCLEAR': 0.03, 'INCONSISTENT': 0.0} | 571.66 | ok |
| heldout (new) | EQ-H12 | 1 | UNCLEAR | 0.76 | {'SUPPORTED': 0.18, 'UNRELATED': 0.0, 'UNCLEAR': 0.82, 'INCONSISTENT': 0.0} | 602.615 | ok |
| heldout (new) | EQ-H13 | 1 | INCONSISTENT | 0.41 | {'SUPPORTED': 0.09, 'UNRELATED': 0.15, 'UNCLEAR': 0.2, 'INCONSISTENT': 0.56} | 617.022 | ok |
| heldout (new) | EQ-H14 | 1 | INCONSISTENT | 0.95 | {'SUPPORTED': 0.03, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.96} | 591.685 | ok |
| heldout (new) | EQ-H15 | 1 | UNRELATED | 0.87 | {'SUPPORTED': 0.01, 'UNRELATED': 0.9, 'UNCLEAR': 0.08, 'INCONSISTENT': 0.01} | 589.318 | ok |
| heldout (new) | EQ-H16 | 1 | UNCLEAR | 0.89 | {'SUPPORTED': 0.08, 'UNRELATED': 0.0, 'UNCLEAR': 0.92, 'INCONSISTENT': 0.0} | 593.883 | ok |
| heldout (new) | EQ-H17 | 1 | UNCLEAR | 0.36 | {'SUPPORTED': 0.44, 'UNRELATED': 0.0, 'UNCLEAR': 0.52, 'INCONSISTENT': 0.04} | 594.581 | ok |
| heldout (new) | EQ-H18 | 1 | SUPPORTED | 0.8 | {'SUPPORTED': 0.85, 'UNRELATED': 0.0, 'UNCLEAR': 0.05, 'INCONSISTENT': 0.1} | 619.519 | ok |
| heldout (new) | EQ-H19 | 1 | SUPPORTED | 0.97 | {'SUPPORTED': 0.98, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.01} | 562.964 | ok |
| heldout (new) | EQ-H20 | 1 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 606.842 | ok |
| heldout (new) | EQ-H08 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 558.711 | ok |
| heldout (new) | EQ-H09 | 2 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.0} | 586.08 | ok |
| heldout (new) | EQ-H10 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 554.616 | ok |
| heldout (new) | EQ-H11 | 2 | SUPPORTED | 0.77 | {'SUPPORTED': 0.83, 'UNRELATED': 0.15, 'UNCLEAR': 0.02, 'INCONSISTENT': 0.0} | 594.343 | ok |
| heldout (new) | EQ-H12 | 2 | UNCLEAR | 0.72 | {'SUPPORTED': 0.21, 'UNRELATED': 0.0, 'UNCLEAR': 0.79, 'INCONSISTENT': 0.0} | 797.204 | ok |
| heldout (new) | EQ-H13 | 2 | INCONSISTENT | 0.37 | {'SUPPORTED': 0.07, 'UNRELATED': 0.23, 'UNCLEAR': 0.17, 'INCONSISTENT': 0.53} | 571.566 | ok |
| heldout (new) | EQ-H14 | 2 | INCONSISTENT | 0.95 | {'SUPPORTED': 0.03, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.96} | 573.59 | ok |
| heldout (new) | EQ-H15 | 2 | UNRELATED | 0.91 | {'SUPPORTED': 0.01, 'UNRELATED': 0.93, 'UNCLEAR': 0.05, 'INCONSISTENT': 0.01} | 567.839 | ok |
| heldout (new) | EQ-H16 | 2 | UNCLEAR | 0.91 | {'SUPPORTED': 0.07, 'UNRELATED': 0.0, 'UNCLEAR': 0.93, 'INCONSISTENT': 0.0} | 567.168 | ok |
| heldout (new) | EQ-H17 | 2 | UNCLEAR | 0.43 | {'SUPPORTED': 0.4, 'UNRELATED': 0.0, 'UNCLEAR': 0.57, 'INCONSISTENT': 0.03} | 566.257 | ok |
| heldout (new) | EQ-H18 | 2 | SUPPORTED | 0.8 | {'SUPPORTED': 0.85, 'UNRELATED': 0.0, 'UNCLEAR': 0.04, 'INCONSISTENT': 0.11} | 574.989 | ok |
| heldout (new) | EQ-H19 | 2 | SUPPORTED | 0.97 | {'SUPPORTED': 0.98, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.01} | 569.621 | ok |
| heldout (new) | EQ-H20 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 553.892 | ok |
| heldout (new) | EQ-H01 | 2 | UNRELATED | 0.88 | {'SUPPORTED': 0.03, 'UNRELATED': 0.91, 'UNCLEAR': 0.05, 'INCONSISTENT': 0.01} | 599.247 | ok |
| heldout (new) | EQ-H02 | 2 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.0} | 606.225 | ok |
| heldout (new) | EQ-H03 | 2 | UNCLEAR | 0.57 | {'SUPPORTED': 0.11, 'UNRELATED': 0.2, 'UNCLEAR': 0.68, 'INCONSISTENT': 0.01} | 585.694 | ok |
| heldout (new) | EQ-H04 | 2 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 669.769 | ok |
| heldout (new) | EQ-H05 | 2 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.01} | 562.002 | ok |
| heldout (new) | EQ-H06 | 2 | UNRELATED | 0.93 | {'SUPPORTED': 0.0, 'UNRELATED': 0.95, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.05} | 612.933 | ok |
| heldout (new) | EQ-H07 | 2 | UNRELATED | 1.0 | {'SUPPORTED': 0.0, 'UNRELATED': 1.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 641.249 | ok |
| heldout (new) | EQ-H15 | 3 | UNRELATED | 0.92 | {'SUPPORTED': 0.01, 'UNRELATED': 0.94, 'UNCLEAR': 0.05, 'INCONSISTENT': 0.0} | 582.906 | ok |
| heldout (new) | EQ-H16 | 3 | UNCLEAR | 0.91 | {'SUPPORTED': 0.07, 'UNRELATED': 0.0, 'UNCLEAR': 0.93, 'INCONSISTENT': 0.0} | 582.721 | ok |
| heldout (new) | EQ-H17 | 3 | UNCLEAR | 0.41 | {'SUPPORTED': 0.43, 'UNRELATED': 0.0, 'UNCLEAR': 0.56, 'INCONSISTENT': 0.01} | 550.988 | ok |
| heldout (new) | EQ-H18 | 3 | SUPPORTED | 0.84 | {'SUPPORTED': 0.88, 'UNRELATED': 0.0, 'UNCLEAR': 0.04, 'INCONSISTENT': 0.08} | 626.625 | ok |
| heldout (new) | EQ-H19 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 569.28 | ok |
| heldout (new) | EQ-H20 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 553.494 | ok |
| heldout (new) | EQ-H01 | 3 | UNRELATED | 0.87 | {'SUPPORTED': 0.04, 'UNRELATED': 0.9, 'UNCLEAR': 0.05, 'INCONSISTENT': 0.01} | 607.548 | ok |
| heldout (new) | EQ-H02 | 3 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.0} | 554.121 | ok |
| heldout (new) | EQ-H03 | 3 | UNCLEAR | 0.59 | {'SUPPORTED': 0.2, 'UNRELATED': 0.1, 'UNCLEAR': 0.69, 'INCONSISTENT': 0.01} | 582.555 | ok |
| heldout (new) | EQ-H04 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 562.6 | ok |
| heldout (new) | EQ-H05 | 3 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.01} | 590.552 | ok |
| heldout (new) | EQ-H06 | 3 | UNRELATED | 0.93 | {'SUPPORTED': 0.0, 'UNRELATED': 0.95, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.05} | 726.48 | ok |
| heldout (new) | EQ-H07 | 3 | UNRELATED | 1.0 | {'SUPPORTED': 0.0, 'UNRELATED': 1.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 564.661 | ok |
| heldout (new) | EQ-H08 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 565.693 | ok |
| heldout (new) | EQ-H09 | 3 | SUPPORTED | 0.99 | {'SUPPORTED': 0.99, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.0} | 601.408 | ok |
| heldout (new) | EQ-H10 | 3 | SUPPORTED | 1.0 | {'SUPPORTED': 1.0, 'UNRELATED': 0.0, 'UNCLEAR': 0.0, 'INCONSISTENT': 0.0} | 586.622 | ok |
| heldout (new) | EQ-H11 | 3 | SUPPORTED | 0.81 | {'SUPPORTED': 0.86, 'UNRELATED': 0.12, 'UNCLEAR': 0.02, 'INCONSISTENT': 0.0} | 585.705 | ok |
| heldout (new) | EQ-H12 | 3 | UNCLEAR | 0.8 | {'SUPPORTED': 0.15, 'UNRELATED': 0.0, 'UNCLEAR': 0.85, 'INCONSISTENT': 0.0} | 565.511 | ok |
| heldout (new) | EQ-H13 | 3 | INCONSISTENT | 0.4 | {'SUPPORTED': 0.08, 'UNRELATED': 0.18, 'UNCLEAR': 0.19, 'INCONSISTENT': 0.55} | 593.378 | ok |
| heldout (new) | EQ-H14 | 3 | INCONSISTENT | 0.95 | {'SUPPORTED': 0.03, 'UNRELATED': 0.0, 'UNCLEAR': 0.01, 'INCONSISTENT': 0.96} | 562.611 | ok |

## Requests, latency, usage and failures

| Split | Request kind | Attempts | Median ms | Recorded input tokens | Recorded cost sum | Requests with cost |
| --- | --- | --- | --- | --- | --- | --- |
| development | signals | 96 | 586.2035000000001 | 99279 | 0.004169718 | 96 |
| development | j2 | 0 | None | 0 | None | 0 |
| heldout | signals | 60 | 583.6285 | 61350 | 0.0025767 | 60 |
| heldout | j2 | 60 | 582.8135 | 58986 | 0.002477412 | 60 |

J3/J4 share a request: per-question price and latency cannot be isolated from this run. B, C and D are offline ablations of shared signal responses, not separately benchmarked deployments. Do not claim measured Noul-only versus Score-only latency/cost. Historical development baseline latency is from a different run, so adding its time to new signals is not a paired causal timing experiment. Reported usage.cost is copied from HTTP bodies without inventing missing costs or assuming currency.

```json
{
  "blocking_reason": null,
  "pending_request": null,
  "execution_errors": [],
  "preflights": [
    {
      "status": "ok",
      "error": null,
      "latency_ms": 283.269
    }
  ],
  "failed_outputs": []
}
```

Full original input states, question objects, response model, HTTP bodies and safe response headers, IDs, provider, usage, confidence, statuses and errors remain in raw_results.json. Pending requests are checkpointed before sending and never silently reissued after an interruption. API failures stay failures. No authorization headers or credential values are saved.

| Split | Case | Trial | Kind | Started UTC | HTTP | Returned model | Response ID | Typed usage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| development | J2-01 | 1 | signals | 2026-10-29T15:41:42.949787+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288503-aF4IzPs6ClLAgmJ9HMPb | {'input_tokens': 1173, 'output_tokens': 42} |
| development | J2-02 | 1 | signals | 2026-10-29T15:41:44.260471+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288503-wzHs9iHflYDPTbD9lNge | {'input_tokens': 1186, 'output_tokens': 42} |
| development | J2-03 | 1 | signals | 2026-10-29T15:41:44.919747+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288504-oEyiMr4mCuwYN8KGCcAA | {'input_tokens': 1180, 'output_tokens': 42} |
| development | J2-04 | 1 | signals | 2026-10-29T15:41:45.617322+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288505-OJwkWg6vjdGLpPLXMO3s | {'input_tokens': 1176, 'output_tokens': 42} |
| development | J2-05 | 1 | signals | 2026-10-29T15:41:46.396591+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288505-kpRyQJxH9bcg8QB7VVcZ | {'input_tokens': 1175, 'output_tokens': 42} |
| development | J2-06 | 1 | signals | 2026-10-29T15:41:47.061944+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288506-svZBrruWaRysxQWB3r3l | {'input_tokens': 1172, 'output_tokens': 42} |
| development | J2-07 | 1 | signals | 2026-10-29T15:41:47.708932+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288507-kaVyXRAyNyyLubp7RTST | {'input_tokens': 1175, 'output_tokens': 42} |
| development | J2-08 | 1 | signals | 2026-10-29T15:41:48.352670+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288507-T0H6W6pALxAdIbzbyYeB | {'input_tokens': 1171, 'output_tokens': 42} |
| development | J2-09 | 1 | signals | 2026-10-29T15:41:49.030777+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288508-y8kRLHK65sUQPALM6sJH | {'input_tokens': 1168, 'output_tokens': 42} |
| development | J2-10 | 1 | signals | 2026-10-29T15:41:49.740406+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288509-Zg2lZvdkiPluff1QMe4A | {'input_tokens': 1187, 'output_tokens': 42} |
| development | J2-11 | 1 | signals | 2026-10-29T15:41:50.534062+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288509-RPG8oRLei2Aeip9Z1NRi | {'input_tokens': 1180, 'output_tokens': 42} |
| development | J2-12 | 1 | signals | 2026-10-29T15:41:51.168758+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288510-SMJdVk4wAXSq4NSwBUdY | {'input_tokens': 1179, 'output_tokens': 42} |
| development | J2-13 | 1 | signals | 2026-10-29T15:41:51.778363+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288511-S8kKVInJ0elhDVoDXM3T | {'input_tokens': 895, 'output_tokens': 42} |
| development | J2-14 | 1 | signals | 2026-10-29T15:41:52.599395+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288512-Srh7G3zmgBzxdpxQGR8P | {'input_tokens': 887, 'output_tokens': 42} |
| development | J2-15 | 1 | signals | 2026-10-29T15:41:53.232649+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288512-T3L37j7XUgQLoTVIS8mu | {'input_tokens': 874, 'output_tokens': 42} |
| development | J2-16 | 1 | signals | 2026-10-29T15:41:53.861607+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288513-JK5V8CWjf7ncgGdd4yWn | {'input_tokens': 891, 'output_tokens': 42} |
| development | J2-17 | 1 | signals | 2026-10-29T15:41:54.527981+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288513-V3uBSPtrWJVvzoQSveAC | {'input_tokens': 901, 'output_tokens': 42} |
| development | J2-18 | 1 | signals | 2026-10-29T15:41:55.254503+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288514-Uy70qpIDbN2vBLpUkS4X | {'input_tokens': 890, 'output_tokens': 42} |
| development | J2-19 | 1 | signals | 2026-10-29T15:41:55.914537+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288515-QPDNsPjXH7rWwNvYLnIa | {'input_tokens': 965, 'output_tokens': 42} |
| development | J2-20 | 1 | signals | 2026-10-29T15:41:56.622020+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288516-kI98yCuJONbl97bFCYtt | {'input_tokens': 966, 'output_tokens': 42} |
| development | J2-21 | 1 | signals | 2026-10-29T15:41:57.284603+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288516-EahN2ZuEc5iLRzs1QOf5 | {'input_tokens': 967, 'output_tokens': 42} |
| development | J2-22 | 1 | signals | 2026-10-29T15:41:57.956872+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288517-xzH5cqFzMlYAboKAcXCk | {'input_tokens': 956, 'output_tokens': 42} |
| development | J2-23 | 1 | signals | 2026-10-29T15:41:58.656618+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288518-jHwJmjGQgiSUa62whsCa | {'input_tokens': 961, 'output_tokens': 42} |
| development | J2-24 | 1 | signals | 2026-10-29T15:41:59.295824+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288518-9ItKt4qpmo2Jhf582dxB | {'input_tokens': 948, 'output_tokens': 42} |
| development | J2-25 | 1 | signals | 2026-10-29T15:42:00.002952+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288519-74GXK7tmc55SAmUiQtmL | {'input_tokens': 958, 'output_tokens': 42} |
| development | J2-26 | 1 | signals | 2026-10-29T15:42:00.709350+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288520-iEYDzr0AvUjT9s9pNMQo | {'input_tokens': 952, 'output_tokens': 42} |
| development | J2-27 | 1 | signals | 2026-10-29T15:42:01.377151+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288520-Kjy8dDGh4MX91WhNziw4 | {'input_tokens': 950, 'output_tokens': 42} |
| development | J2-28 | 1 | signals | 2026-10-29T15:42:02.078694+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288521-TalyfN6MlbcCAVIeiLSE | {'input_tokens': 957, 'output_tokens': 42} |
| development | J2-29 | 1 | signals | 2026-10-29T15:42:02.725976+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288522-bbQB40KJPydXGYQSY1Xf | {'input_tokens': 943, 'output_tokens': 42} |
| development | J2-30 | 1 | signals | 2026-10-29T15:42:03.346336+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288522-WDwqz50oT3sj6hFkXMuQ | {'input_tokens': 949, 'output_tokens': 42} |
| development | J2-31 | 1 | signals | 2026-10-29T15:42:04.096643+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288523-xlhft7IxibzcyG3pALqs | {'input_tokens': 1190, 'output_tokens': 42} |
| development | J2-32 | 1 | signals | 2026-10-29T15:42:04.734321+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288524-8dzg6KeA96qDAUgCgvky | {'input_tokens': 971, 'output_tokens': 42} |
| development | J2-08 | 2 | signals | 2026-10-29T15:42:05.368763+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288524-krL8b2zDCV4clB5KHRRw | {'input_tokens': 1171, 'output_tokens': 42} |
| development | J2-09 | 2 | signals | 2026-10-29T15:42:06.080044+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288525-Es7fY8PgZExSRtLa6QAb | {'input_tokens': 1168, 'output_tokens': 42} |
| development | J2-10 | 2 | signals | 2026-10-29T15:42:06.732676+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288526-2jV8rwOPu94kE5vSZR2j | {'input_tokens': 1187, 'output_tokens': 42} |
| development | J2-11 | 2 | signals | 2026-10-29T15:42:07.397310+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288526-30BRdDVFGgKSK4QYo9c1 | {'input_tokens': 1180, 'output_tokens': 42} |
| development | J2-12 | 2 | signals | 2026-10-29T15:42:08.105903+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288527-hIrG9nEeLVcuPbbVPl0v | {'input_tokens': 1179, 'output_tokens': 42} |
| development | J2-13 | 2 | signals | 2026-10-29T15:42:08.744220+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288528-0zFSLTWwGNhvwXhnQvwx | {'input_tokens': 895, 'output_tokens': 42} |
| development | J2-14 | 2 | signals | 2026-10-29T15:42:09.402167+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288528-XJ21PiwWGsluY34ovWVC | {'input_tokens': 887, 'output_tokens': 42} |
| development | J2-15 | 2 | signals | 2026-10-29T15:42:10.128502+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288529-Trr9VYFDKvgW2LCtI79B | {'input_tokens': 874, 'output_tokens': 42} |
| development | J2-16 | 2 | signals | 2026-10-29T15:42:10.800016+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288530-P64dO75e6VenmjuYaGnB | {'input_tokens': 891, 'output_tokens': 42} |
| development | J2-17 | 2 | signals | 2026-10-29T15:42:11.421784+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288530-MQLLdsV6qz0eJl0Ay3rp | {'input_tokens': 901, 'output_tokens': 42} |
| development | J2-18 | 2 | signals | 2026-10-29T15:42:12.109111+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288531-oGcILmzW1DSTibC7E5Jo | {'input_tokens': 890, 'output_tokens': 42} |
| development | J2-19 | 2 | signals | 2026-10-29T15:42:12.767525+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288532-IUDH2dDqyz7jHmt7oaXC | {'input_tokens': 965, 'output_tokens': 42} |
| development | J2-20 | 2 | signals | 2026-10-29T15:42:13.425899+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288532-oWgTTQjAop29Qw59RUVg | {'input_tokens': 966, 'output_tokens': 42} |
| development | J2-21 | 2 | signals | 2026-10-29T15:42:14.067748+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288533-Ptx6Oausl871H0f0Ldus | {'input_tokens': 967, 'output_tokens': 42} |
| development | J2-22 | 2 | signals | 2026-10-29T15:42:14.766655+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288534-kUaBzDwnRtt77ACiUelE | {'input_tokens': 956, 'output_tokens': 42} |
| development | J2-23 | 2 | signals | 2026-10-29T15:42:15.449444+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288534-vDeTt4zqhFJSQVODICEA | {'input_tokens': 961, 'output_tokens': 42} |
| development | J2-24 | 2 | signals | 2026-10-29T15:42:16.134772+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288535-lqx9S1iA2MVyKuXSjOHn | {'input_tokens': 948, 'output_tokens': 42} |
| development | J2-25 | 2 | signals | 2026-10-29T15:42:16.848002+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288536-7zNPJJMlfyQtmLXGV7Zf | {'input_tokens': 958, 'output_tokens': 42} |
| development | J2-26 | 2 | signals | 2026-10-29T15:42:17.519048+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288536-CooBLpaEMvSEtXhp8UEl | {'input_tokens': 952, 'output_tokens': 42} |
| development | J2-27 | 2 | signals | 2026-10-29T15:42:18.210902+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288537-poy0p8VD3ALMloeBetPE | {'input_tokens': 950, 'output_tokens': 42} |
| development | J2-28 | 2 | signals | 2026-10-29T15:42:18.923176+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288538-HvrR8zdZpaR4D1g0LB97 | {'input_tokens': 957, 'output_tokens': 42} |
| development | J2-29 | 2 | signals | 2026-10-29T15:42:19.577678+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288538-0PCacDizY6tUJkSciGoh | {'input_tokens': 943, 'output_tokens': 42} |
| development | J2-30 | 2 | signals | 2026-10-29T15:42:20.216199+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288539-m2CPRX1c5w7ynf3GwzfE | {'input_tokens': 949, 'output_tokens': 42} |
| development | J2-31 | 2 | signals | 2026-10-29T15:42:20.899533+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288540-8XzLtXHwC9O4BAehI8Aa | {'input_tokens': 1190, 'output_tokens': 42} |
| development | J2-32 | 2 | signals | 2026-10-29T15:42:21.561018+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288540-IOPvnxIaUYL8VM1TqaTk | {'input_tokens': 971, 'output_tokens': 42} |
| development | J2-01 | 2 | signals | 2026-10-29T15:42:22.222852+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288541-j6GiiNv0xISFbHHZTOXV | {'input_tokens': 1173, 'output_tokens': 42} |
| development | J2-02 | 2 | signals | 2026-10-29T15:42:22.865332+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288542-DHjuqyKdmRRA48ucDdzU | {'input_tokens': 1186, 'output_tokens': 42} |
| development | J2-03 | 2 | signals | 2026-10-29T15:42:23.542836+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288542-Iw7gBbagzrHdDQAwHASs | {'input_tokens': 1180, 'output_tokens': 42} |
| development | J2-04 | 2 | signals | 2026-10-29T15:42:24.186929+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288543-2v9N7OXSjEPRxqJ5ctCw | {'input_tokens': 1176, 'output_tokens': 42} |
| development | J2-05 | 2 | signals | 2026-10-29T15:42:24.897398+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288544-pGkAbZSMqQDsN9TW2mFr | {'input_tokens': 1175, 'output_tokens': 42} |
| development | J2-06 | 2 | signals | 2026-10-29T15:42:25.571746+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288544-qyNQa2tgD3RnwAv2i4J3 | {'input_tokens': 1172, 'output_tokens': 42} |
| development | J2-07 | 2 | signals | 2026-10-29T15:42:26.238886+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288545-FFBew3mc3cqMihVqaoy5 | {'input_tokens': 1175, 'output_tokens': 42} |
| development | J2-15 | 3 | signals | 2026-10-29T15:42:26.918301+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288546-UkEvDys4zdldZZHH7f39 | {'input_tokens': 874, 'output_tokens': 42} |
| development | J2-16 | 3 | signals | 2026-10-29T15:42:27.617781+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288547-negb9RmfBTu6x41xKsPo | {'input_tokens': 891, 'output_tokens': 42} |
| development | J2-17 | 3 | signals | 2026-10-29T15:42:28.287750+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288547-mmVcFYVL1NK2KifD3AWT | {'input_tokens': 901, 'output_tokens': 42} |
| development | J2-18 | 3 | signals | 2026-10-29T15:42:28.958148+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288548-tEuoNBv7WK1k9QsW44hJ | {'input_tokens': 890, 'output_tokens': 42} |
| development | J2-19 | 3 | signals | 2026-10-29T15:42:29.628740+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288549-EG4FNiYCyNEGPfmI1lWf | {'input_tokens': 965, 'output_tokens': 42} |
| development | J2-20 | 3 | signals | 2026-10-29T15:42:30.296662+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288549-UmwbraLbO9AopPHRYCu9 | {'input_tokens': 966, 'output_tokens': 42} |
| development | J2-21 | 3 | signals | 2026-10-29T15:42:30.999150+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288550-CPvo9gfS3zR7HY4tOUGi | {'input_tokens': 967, 'output_tokens': 42} |
| development | J2-22 | 3 | signals | 2026-10-29T15:42:31.684415+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288551-AvEdIswsQNSv1ydmR2Sh | {'input_tokens': 956, 'output_tokens': 42} |
| development | J2-23 | 3 | signals | 2026-10-29T15:42:32.385209+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288551-iPBBLUu3JKGAWnmmtWY2 | {'input_tokens': 961, 'output_tokens': 42} |
| development | J2-24 | 3 | signals | 2026-10-29T15:42:33.071046+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288552-51yviHfte13TGcJoaS8J | {'input_tokens': 948, 'output_tokens': 42} |
| development | J2-25 | 3 | signals | 2026-10-29T15:42:33.743787+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288553-DC5f04FQSYjAuOlStNpU | {'input_tokens': 958, 'output_tokens': 42} |
| development | J2-26 | 3 | signals | 2026-10-29T15:42:34.538022+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288553-peeIRVtW7fsAfoRP4LgG | {'input_tokens': 952, 'output_tokens': 42} |
| development | J2-27 | 3 | signals | 2026-10-29T15:42:35.231737+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288554-MXX306w5RSxU438a8ovE | {'input_tokens': 950, 'output_tokens': 42} |
| development | J2-28 | 3 | signals | 2026-10-29T15:42:35.925109+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288555-VSomPnTWivHgKg9FKxY2 | {'input_tokens': 957, 'output_tokens': 42} |
| development | J2-29 | 3 | signals | 2026-10-29T15:42:36.596802+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288555-XmNyCWL87jR9S5prY33u | {'input_tokens': 943, 'output_tokens': 42} |
| development | J2-30 | 3 | signals | 2026-10-29T15:42:37.294762+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288556-4riFOb3hLeF26WTrkIGN | {'input_tokens': 949, 'output_tokens': 42} |
| development | J2-31 | 3 | signals | 2026-10-29T15:42:38.004471+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288557-IAXatIuq5TvdbEuydWKx | {'input_tokens': 1190, 'output_tokens': 42} |
| development | J2-32 | 3 | signals | 2026-10-29T15:42:38.778893+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288558-NQTpEb14nJ7dMNkhXAXP | {'input_tokens': 971, 'output_tokens': 42} |
| development | J2-01 | 3 | signals | 2026-10-29T15:42:39.609214+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288559-KjDuZ0HEsjlk0gdwC5RS | {'input_tokens': 1173, 'output_tokens': 42} |
| development | J2-02 | 3 | signals | 2026-10-29T15:42:40.314828+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288559-1bKwoiiRdhDj9pq3iZNw | {'input_tokens': 1186, 'output_tokens': 42} |
| development | J2-03 | 3 | signals | 2026-10-29T15:42:40.948228+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288560-Dr5xsPW26rWKNDZQCxqA | {'input_tokens': 1180, 'output_tokens': 42} |
| development | J2-04 | 3 | signals | 2026-10-29T15:42:41.696506+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288561-cHK6DkBD1m3UrUDZHu6k | {'input_tokens': 1176, 'output_tokens': 42} |
| development | J2-05 | 3 | signals | 2026-10-29T15:42:42.472443+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288561-xDySl0O78xudEwEvgOT6 | {'input_tokens': 1175, 'output_tokens': 42} |
| development | J2-06 | 3 | signals | 2026-10-29T15:42:43.131348+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288562-f2t6CiWco9O8hHFx5smP | {'input_tokens': 1172, 'output_tokens': 42} |
| development | J2-07 | 3 | signals | 2026-10-29T15:42:43.953213+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288563-9P6mIz8uu0o7OzH45BlA | {'input_tokens': 1175, 'output_tokens': 42} |
| development | J2-08 | 3 | signals | 2026-10-29T15:42:44.647583+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288564-Xsb4TiKaPFQeBObeeNFN | {'input_tokens': 1171, 'output_tokens': 42} |
| development | J2-09 | 3 | signals | 2026-10-29T15:42:45.391498+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288564-RE6wWO3k7hIYibR0u4HK | {'input_tokens': 1168, 'output_tokens': 42} |
| development | J2-10 | 3 | signals | 2026-10-29T15:42:46.066538+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288565-SK0ELcsFOletIxX1jYRj | {'input_tokens': 1187, 'output_tokens': 42} |
| development | J2-11 | 3 | signals | 2026-10-29T15:42:46.784720+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288566-YktR8Rrpi0oePmyUZjBh | {'input_tokens': 1180, 'output_tokens': 42} |
| development | J2-12 | 3 | signals | 2026-10-29T15:42:47.452082+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288566-bOlqekVSdxp3gNcHZk5k | {'input_tokens': 1179, 'output_tokens': 42} |
| development | J2-13 | 3 | signals | 2026-10-29T15:42:48.186775+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288567-UD14GztkIwXE9D5GnorJ | {'input_tokens': 895, 'output_tokens': 42} |
| development | J2-14 | 3 | signals | 2026-10-29T15:42:49.025902+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288568-xoNp8tXujHp9kbxhYYdC | {'input_tokens': 887, 'output_tokens': 42} |
| heldout | EQ-H01 | 1 | j2 | 2026-10-29T15:42:49.791510+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288569-owwInzTyQwkRDNLhueUX | {'input_tokens': 958, 'output_tokens': 57} |
| heldout | EQ-H01 | 1 | signals | 2026-10-29T15:42:50.742433+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288570-Wxr2yWkQsnQyCdIkSvE9 | {'input_tokens': 963, 'output_tokens': 42} |
| heldout | EQ-H02 | 1 | signals | 2026-10-29T15:42:51.645702+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288571-3H22cUzVPa9tSPyPCTgg | {'input_tokens': 957, 'output_tokens': 42} |
| heldout | EQ-H02 | 1 | j2 | 2026-10-29T15:42:52.379811+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288571-Fw2BvhSIMVByEO7sHDPG | {'input_tokens': 952, 'output_tokens': 57} |
| heldout | EQ-H03 | 1 | j2 | 2026-10-29T15:42:53.066233+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288572-2WWmGmYrt1HJsjsl1yHy | {'input_tokens': 955, 'output_tokens': 57} |
| heldout | EQ-H03 | 1 | signals | 2026-10-29T15:42:53.734606+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288573-hOV91Ln06xDJygWV0cUA | {'input_tokens': 960, 'output_tokens': 42} |
| heldout | EQ-H04 | 1 | signals | 2026-10-29T15:42:54.553029+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288573-nqtUNUjTWV8Ajx6FbYlc | {'input_tokens': 953, 'output_tokens': 42} |
| heldout | EQ-H04 | 1 | j2 | 2026-10-29T15:42:55.250180+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288574-1lZnk7KUiPoTFB64BHr1 | {'input_tokens': 948, 'output_tokens': 57} |
| heldout | EQ-H05 | 1 | j2 | 2026-10-29T15:42:56.100020+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288575-AaYZxfUoSJm6l36d9uTH | {'input_tokens': 957, 'output_tokens': 57} |
| heldout | EQ-H05 | 1 | signals | 2026-10-29T15:42:56.780661+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288576-F0yRyvqHH3SENFCkMz1l | {'input_tokens': 969, 'output_tokens': 42} |
| heldout | EQ-H06 | 1 | signals | 2026-10-29T15:42:57.466288+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288576-0BTnLeZCibgeWdPdIR8B | {'input_tokens': 1184, 'output_tokens': 42} |
| heldout | EQ-H06 | 1 | j2 | 2026-10-29T15:42:58.198238+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288577-P3DSPrim70MF9KWnDgoT | {'input_tokens': 1064, 'output_tokens': 57} |
| heldout | EQ-H07 | 1 | j2 | 2026-10-29T15:42:58.900749+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288578-1mazUpXUQZePl3EaDFcx | {'input_tokens': 1088, 'output_tokens': 57} |
| heldout | EQ-H07 | 1 | signals | 2026-10-29T15:42:59.619788+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288579-0ElLzGUeLVNFf95RA8lq | {'input_tokens': 1208, 'output_tokens': 42} |
| heldout | EQ-H08 | 1 | signals | 2026-10-29T15:43:00.353534+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288579-LfSP0KPJsSbPIVhQjFg9 | {'input_tokens': 1170, 'output_tokens': 42} |
| heldout | EQ-H08 | 1 | j2 | 2026-10-29T15:43:01.021982+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288580-qa6XlARuRZFBhot99qZi | {'input_tokens': 1050, 'output_tokens': 57} |
| heldout | EQ-H09 | 1 | j2 | 2026-10-29T15:43:01.735596+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288581-XmNwcgl8pDoLliw8WglW | {'input_tokens': 911, 'output_tokens': 57} |
| heldout | EQ-H09 | 1 | signals | 2026-10-29T15:43:02.412925+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288581-mJBURXxgkvftJB5zzGAS | {'input_tokens': 883, 'output_tokens': 42} |
| heldout | EQ-H10 | 1 | signals | 2026-10-29T15:43:03.114254+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288582-6O0qnvkRd7fzqv99b3t4 | {'input_tokens': 866, 'output_tokens': 42} |
| heldout | EQ-H10 | 1 | j2 | 2026-10-29T15:43:03.815875+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288583-M9rYNnS2VF6RtPViRYRh | {'input_tokens': 904, 'output_tokens': 57} |
| heldout | EQ-H11 | 1 | j2 | 2026-10-29T15:43:04.487840+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288583-fId2k13KONL0IkvpS09A | {'input_tokens': 921, 'output_tokens': 57} |
| heldout | EQ-H11 | 1 | signals | 2026-10-29T15:43:05.189669+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288584-y7FWUPdcCwjMPv6ZHsrv | {'input_tokens': 895, 'output_tokens': 42} |
| heldout | EQ-H12 | 1 | signals | 2026-10-29T15:43:05.888915+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288585-ndssDz9IbTvJLbPfHW1a | {'input_tokens': 880, 'output_tokens': 42} |
| heldout | EQ-H12 | 1 | j2 | 2026-10-29T15:43:06.631811+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288586-jQtoNsr25jasw55dRfJB | {'input_tokens': 906, 'output_tokens': 57} |
| heldout | EQ-H13 | 1 | j2 | 2026-10-29T15:43:07.364850+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288586-1C4VgYtSIChDLOkEk5lQ | {'input_tokens': 1065, 'output_tokens': 58} |
| heldout | EQ-H13 | 1 | signals | 2026-10-29T15:43:08.097409+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288587-nhp2WVSOKK9q1Hoe4TEa | {'input_tokens': 1185, 'output_tokens': 42} |
| heldout | EQ-H14 | 1 | signals | 2026-10-29T15:43:08.830854+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288588-MOmSToq8cOntAVEJ0TtB | {'input_tokens': 1190, 'output_tokens': 42} |
| heldout | EQ-H14 | 1 | j2 | 2026-10-29T15:43:09.566903+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288588-GQ97pRHWjkt57NrppaJR | {'input_tokens': 1070, 'output_tokens': 58} |
| heldout | EQ-H15 | 1 | j2 | 2026-10-29T15:43:10.281192+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288589-hCzg8eDXS9YzeVVSd7d0 | {'input_tokens': 952, 'output_tokens': 57} |
| heldout | EQ-H15 | 1 | signals | 2026-10-29T15:43:11.000309+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288590-ejUSURZ6nXyoWvvLD0qA | {'input_tokens': 964, 'output_tokens': 42} |
| heldout | EQ-H16 | 1 | signals | 2026-10-29T15:43:11.701111+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288591-kLMU1ibvWItfRrUH2b3l | {'input_tokens': 943, 'output_tokens': 42} |
| heldout | EQ-H16 | 1 | j2 | 2026-10-29T15:43:12.420178+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288591-vmpQTJKwS1ZgITjd7RhW | {'input_tokens': 938, 'output_tokens': 57} |
| heldout | EQ-H17 | 1 | j2 | 2026-10-29T15:43:13.162146+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288592-qVcPLaTSTjFR1LcfHxXB | {'input_tokens': 944, 'output_tokens': 57} |
| heldout | EQ-H17 | 1 | signals | 2026-10-29T15:43:13.878641+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288593-gwL6xgNWHV8e0vciDxYz | {'input_tokens': 956, 'output_tokens': 42} |
| heldout | EQ-H18 | 1 | signals | 2026-10-29T15:43:14.640140+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288594-97cJcchoxX1wNqRYvPLz | {'input_tokens': 963, 'output_tokens': 42} |
| heldout | EQ-H18 | 1 | j2 | 2026-10-29T15:43:15.313599+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288594-VkMF2X7MQSJPVGunIj9r | {'input_tokens': 958, 'output_tokens': 57} |
| heldout | EQ-H19 | 1 | j2 | 2026-10-29T15:43:16.063894+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288595-vI91vlUCaPKh7nmzkaIV | {'input_tokens': 1053, 'output_tokens': 57} |
| heldout | EQ-H19 | 1 | signals | 2026-10-29T15:43:16.767428+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288596-nCICkGvowl6vvE5IHSJS | {'input_tokens': 1173, 'output_tokens': 42} |
| heldout | EQ-H20 | 1 | signals | 2026-10-29T15:43:17.450455+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288596-THE0PJH1IEQqyTWXhF4a | {'input_tokens': 1188, 'output_tokens': 42} |
| heldout | EQ-H20 | 1 | j2 | 2026-10-29T15:43:18.169377+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288597-430klEKK7bq24G8DB2mE | {'input_tokens': 1068, 'output_tokens': 57} |
| heldout | EQ-H08 | 2 | signals | 2026-10-29T15:43:18.903438+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288598-PTEyqX0iDfxTmXJFI8pE | {'input_tokens': 1170, 'output_tokens': 42} |
| heldout | EQ-H08 | 2 | j2 | 2026-10-29T15:43:19.639214+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288599-jrYLYNy2wIzemgyElTqs | {'input_tokens': 1050, 'output_tokens': 57} |
| heldout | EQ-H09 | 2 | j2 | 2026-10-29T15:43:20.350722+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288599-58uypWpaSQWGFeSeOj5j | {'input_tokens': 911, 'output_tokens': 57} |
| heldout | EQ-H09 | 2 | signals | 2026-10-29T15:43:21.057833+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288600-ihs7LmYcYSWUetOXX3j2 | {'input_tokens': 883, 'output_tokens': 42} |
| heldout | EQ-H10 | 2 | signals | 2026-10-29T15:43:21.787024+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288601-A1sH0lTj5VJ0B05Nxjml | {'input_tokens': 866, 'output_tokens': 42} |
| heldout | EQ-H10 | 2 | j2 | 2026-10-29T15:43:22.506873+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288601-5yNddrePVreGDB7mreF9 | {'input_tokens': 904, 'output_tokens': 57} |
| heldout | EQ-H11 | 2 | j2 | 2026-10-29T15:43:23.210609+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288602-p4hxmiP8vGGYVtQi7ybR | {'input_tokens': 921, 'output_tokens': 57} |
| heldout | EQ-H11 | 2 | signals | 2026-10-29T15:43:23.941075+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288603-k4vFIl6lK04nHma9Q6Lq | {'input_tokens': 895, 'output_tokens': 42} |
| heldout | EQ-H12 | 2 | signals | 2026-10-29T15:43:24.658605+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288604-HMkl8TmhY1xxgp452wsZ | {'input_tokens': 880, 'output_tokens': 42} |
| heldout | EQ-H12 | 2 | j2 | 2026-10-29T15:43:25.423085+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288604-ytQ0GLOggirTLGQ9CGJN | {'input_tokens': 906, 'output_tokens': 57} |
| heldout | EQ-H13 | 2 | j2 | 2026-10-29T15:43:26.458718+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288605-sCIGnFJUU7CTIEeWrKyC | {'input_tokens': 1065, 'output_tokens': 58} |
| heldout | EQ-H13 | 2 | signals | 2026-10-29T15:43:27.178840+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288606-d7gPKdtcJ2ox74VEQcDH | {'input_tokens': 1185, 'output_tokens': 42} |
| heldout | EQ-H14 | 2 | signals | 2026-10-29T15:43:27.882801+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288607-YMWQQlij3T9mRPKBLVUY | {'input_tokens': 1190, 'output_tokens': 42} |
| heldout | EQ-H14 | 2 | j2 | 2026-10-29T15:43:28.652222+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288608-HEjP9YRUqS5epjpRJKtV | {'input_tokens': 1070, 'output_tokens': 58} |
| heldout | EQ-H15 | 2 | j2 | 2026-10-29T15:43:29.413473+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288608-pcHWl0jW5uJjacRJSanx | {'input_tokens': 952, 'output_tokens': 57} |
| heldout | EQ-H15 | 2 | signals | 2026-10-29T15:43:30.132748+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288609-HvDU0CZBXv3IlT97ceLW | {'input_tokens': 964, 'output_tokens': 42} |
| heldout | EQ-H16 | 2 | signals | 2026-10-29T15:43:30.911667+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288610-ygtecGlxrWIk1MuIRnCw | {'input_tokens': 943, 'output_tokens': 42} |
| heldout | EQ-H16 | 2 | j2 | 2026-10-29T15:43:31.724534+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288611-tA7MxTIx4xHzvYUvxcD2 | {'input_tokens': 938, 'output_tokens': 57} |
| heldout | EQ-H17 | 2 | j2 | 2026-10-29T15:43:32.424218+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288611-d1Prt7YIDod4tQrml69U | {'input_tokens': 944, 'output_tokens': 57} |
| heldout | EQ-H17 | 2 | signals | 2026-10-29T15:43:33.141787+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288612-sCmgInvVhnYtTJ2uqNhc | {'input_tokens': 956, 'output_tokens': 42} |
| heldout | EQ-H18 | 2 | signals | 2026-10-29T15:43:33.856550+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288613-jr5JsD3XmopwWG2bAMsX | {'input_tokens': 963, 'output_tokens': 42} |
| heldout | EQ-H18 | 2 | j2 | 2026-10-29T15:43:34.556718+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288613-t3DQ7DXEWG5U3zJzqYI7 | {'input_tokens': 958, 'output_tokens': 57} |
| heldout | EQ-H19 | 2 | j2 | 2026-10-29T15:43:35.275685+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288614-667syHScgjBg4lMPjF30 | {'input_tokens': 1053, 'output_tokens': 57} |
| heldout | EQ-H19 | 2 | signals | 2026-10-29T15:43:35.989621+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288615-K5AttbAg9WqR6Gt7x4n7 | {'input_tokens': 1173, 'output_tokens': 42} |
| heldout | EQ-H20 | 2 | signals | 2026-10-29T15:43:36.721012+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288616-5zaJVkcVFrMO1ntZsqZs | {'input_tokens': 1188, 'output_tokens': 42} |
| heldout | EQ-H20 | 2 | j2 | 2026-10-29T15:43:37.469770+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288616-dFNFDdbIaHDOksWyG28L | {'input_tokens': 1068, 'output_tokens': 57} |
| heldout | EQ-H01 | 2 | j2 | 2026-10-29T15:43:38.169068+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288617-m7OeyE08ZfEqEB2vONKy | {'input_tokens': 958, 'output_tokens': 57} |
| heldout | EQ-H01 | 2 | signals | 2026-10-29T15:43:38.919317+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288618-CIgwxxIa6yLQjjacH3md | {'input_tokens': 963, 'output_tokens': 42} |
| heldout | EQ-H02 | 2 | signals | 2026-10-29T15:43:39.661354+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288619-h81NzTRYFgpcbwPxhc7H | {'input_tokens': 957, 'output_tokens': 42} |
| heldout | EQ-H02 | 2 | j2 | 2026-10-29T15:43:41.688226+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288621-NZpQLBq6B7pYHun9gHzh | {'input_tokens': 952, 'output_tokens': 57} |
| heldout | EQ-H03 | 2 | j2 | 2026-10-29T15:43:42.436235+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288621-vI6CWZjZzPr2lOGmbar1 | {'input_tokens': 955, 'output_tokens': 57} |
| heldout | EQ-H03 | 2 | signals | 2026-10-29T15:43:43.532222+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288622-YvlkoqOxI66JzWAM71RK | {'input_tokens': 960, 'output_tokens': 42} |
| heldout | EQ-H04 | 2 | signals | 2026-10-29T15:43:44.281034+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288623-HyHcLkjQ7DunlUltUxzY | {'input_tokens': 953, 'output_tokens': 42} |
| heldout | EQ-H04 | 2 | j2 | 2026-10-29T15:43:45.013324+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288624-EhzbRuZKvxR3wnwrfdRa | {'input_tokens': 948, 'output_tokens': 57} |
| heldout | EQ-H05 | 2 | j2 | 2026-10-29T15:43:45.906659+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288625-uOMgGoum7IgusLdfvvO8 | {'input_tokens': 957, 'output_tokens': 57} |
| heldout | EQ-H05 | 2 | signals | 2026-10-29T15:43:46.650699+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288626-VSeORgqlT00JviF7uZYh | {'input_tokens': 969, 'output_tokens': 42} |
| heldout | EQ-H06 | 2 | signals | 2026-10-29T15:43:47.415527+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288626-AoesOdaghdVYUZcL7elZ | {'input_tokens': 1184, 'output_tokens': 42} |
| heldout | EQ-H06 | 2 | j2 | 2026-10-29T15:43:49.141987+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288628-IBtSuINl8D0X7KQE1r1q | {'input_tokens': 1064, 'output_tokens': 57} |
| heldout | EQ-H07 | 2 | j2 | 2026-10-29T15:43:49.921747+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288629-6kY3waCfQ3RQeblP32T6 | {'input_tokens': 1088, 'output_tokens': 57} |
| heldout | EQ-H07 | 2 | signals | 2026-10-29T15:43:50.726327+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288630-Yl4CqVaVbG6lxrXtjRvC | {'input_tokens': 1208, 'output_tokens': 42} |
| heldout | EQ-H15 | 3 | j2 | 2026-10-29T15:43:51.528363+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288630-G7tPdMBwDqpi1K7u4KeN | {'input_tokens': 952, 'output_tokens': 57} |
| heldout | EQ-H15 | 3 | signals | 2026-10-29T15:43:52.263625+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288631-3Sp34CaM8ceAJrukf7dL | {'input_tokens': 964, 'output_tokens': 42} |
| heldout | EQ-H16 | 3 | signals | 2026-10-29T15:43:52.992780+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288632-QaRm3ep95H2WMMKBqoP3 | {'input_tokens': 943, 'output_tokens': 42} |
| heldout | EQ-H16 | 3 | j2 | 2026-10-29T15:43:53.726257+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288633-dxHhU7iucQbquwKKPqWU | {'input_tokens': 938, 'output_tokens': 57} |
| heldout | EQ-H17 | 3 | j2 | 2026-10-29T15:43:54.457227+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288633-PXA6vFOb4QDOZZisYRXK | {'input_tokens': 944, 'output_tokens': 57} |
| heldout | EQ-H17 | 3 | signals | 2026-10-29T15:43:55.173050+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288634-lK20x9H0tGPz99A4UaLt | {'input_tokens': 956, 'output_tokens': 42} |
| heldout | EQ-H18 | 3 | signals | 2026-10-29T15:43:55.968471+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288635-mqwz5opQxCOdz1dvU2qF | {'input_tokens': 963, 'output_tokens': 42} |
| heldout | EQ-H18 | 3 | j2 | 2026-10-29T15:43:56.717240+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288636-g2ZNvVdEAS5vzy0kkZUj | {'input_tokens': 958, 'output_tokens': 57} |
| heldout | EQ-H19 | 3 | j2 | 2026-10-29T15:43:57.501258+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288636-2Lmpt3tKYPeb681vcKdI | {'input_tokens': 1053, 'output_tokens': 57} |
| heldout | EQ-H19 | 3 | signals | 2026-10-29T15:43:58.230883+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288637-Z3jSIyrsSxKMGrRwMqZq | {'input_tokens': 1173, 'output_tokens': 42} |
| heldout | EQ-H20 | 3 | signals | 2026-10-29T15:43:58.992661+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288638-HqEwwJOPD7T6Whxau8pN | {'input_tokens': 1188, 'output_tokens': 42} |
| heldout | EQ-H20 | 3 | j2 | 2026-10-29T15:43:59.759245+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288639-yJsBVqKOt0z3PIcm6XHp | {'input_tokens': 1068, 'output_tokens': 57} |
| heldout | EQ-H01 | 3 | j2 | 2026-10-29T15:44:00.488946+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288639-SPf36qZjRKjRRXx9qWXu | {'input_tokens': 958, 'output_tokens': 57} |
| heldout | EQ-H01 | 3 | signals | 2026-10-29T15:44:01.284785+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288640-ZjkZPa5eVETHZsnIKhmq | {'input_tokens': 963, 'output_tokens': 42} |
| heldout | EQ-H02 | 3 | signals | 2026-10-29T15:44:02.032428+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288641-2olrw925642b1fTejoUf | {'input_tokens': 957, 'output_tokens': 42} |
| heldout | EQ-H02 | 3 | j2 | 2026-10-29T15:44:02.782421+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288642-klJtAcOjVIEiMo06iOO6 | {'input_tokens': 952, 'output_tokens': 57} |
| heldout | EQ-H03 | 3 | j2 | 2026-10-29T15:44:03.517985+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288642-iOghsP2RfqW6EgAPDZ9V | {'input_tokens': 955, 'output_tokens': 57} |
| heldout | EQ-H03 | 3 | signals | 2026-10-29T15:44:04.292581+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288643-TaHNJwaOQwVpQI1bVfVn | {'input_tokens': 960, 'output_tokens': 42} |
| heldout | EQ-H04 | 3 | signals | 2026-10-29T15:44:05.100641+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288644-ag0F94irl63gIY37gYFC | {'input_tokens': 953, 'output_tokens': 42} |
| heldout | EQ-H04 | 3 | j2 | 2026-10-29T15:44:05.858959+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288645-In5PcxkrbfOcUU1Jfuyv | {'input_tokens': 948, 'output_tokens': 57} |
| heldout | EQ-H05 | 3 | j2 | 2026-10-29T15:44:06.583667+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288645-65Kfj0vp3N47BU4aV2Zd | {'input_tokens': 957, 'output_tokens': 57} |
| heldout | EQ-H05 | 3 | signals | 2026-10-29T15:44:07.331101+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288646-hwPdNbBPXIeiCc4C3cY3 | {'input_tokens': 969, 'output_tokens': 42} |
| heldout | EQ-H06 | 3 | signals | 2026-10-29T15:44:08.063668+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288647-Rjurofyj24tEn1yxhM87 | {'input_tokens': 1184, 'output_tokens': 42} |
| heldout | EQ-H06 | 3 | j2 | 2026-10-29T15:44:08.795367+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288648-mjm6BdFLXvJj6lVJv13G | {'input_tokens': 1064, 'output_tokens': 57} |
| heldout | EQ-H07 | 3 | j2 | 2026-10-29T15:44:09.694232+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288649-XjA9i6UGHQYn8CQ2y6Cq | {'input_tokens': 1088, 'output_tokens': 57} |
| heldout | EQ-H07 | 3 | signals | 2026-10-29T15:44:10.525855+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288649-ENoPNUakVqxssrKffKwV | {'input_tokens': 1208, 'output_tokens': 42} |
| heldout | EQ-H08 | 3 | signals | 2026-10-29T15:44:11.247123+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288650-NWvQDj8aFNmXNBfHmEhv | {'input_tokens': 1170, 'output_tokens': 42} |
| heldout | EQ-H08 | 3 | j2 | 2026-10-29T15:44:11.990407+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288651-coZ028LiRTGH2Yijc7hc | {'input_tokens': 1050, 'output_tokens': 57} |
| heldout | EQ-H09 | 3 | j2 | 2026-10-29T15:44:12.709413+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288652-oeGySKhi5SWV53yv4kub | {'input_tokens': 911, 'output_tokens': 57} |
| heldout | EQ-H09 | 3 | signals | 2026-10-29T15:44:13.490755+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288652-WbTy6dQkZwN8s3fKDWp6 | {'input_tokens': 883, 'output_tokens': 42} |
| heldout | EQ-H10 | 3 | signals | 2026-10-29T15:44:14.238006+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288653-U05QWnp8sLwk823qHkjD | {'input_tokens': 866, 'output_tokens': 42} |
| heldout | EQ-H10 | 3 | j2 | 2026-10-29T15:44:15.010117+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288654-WYMDs9GqbcJEGcngTwDl | {'input_tokens': 904, 'output_tokens': 57} |
| heldout | EQ-H11 | 3 | j2 | 2026-10-29T15:44:15.772771+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288655-LXXf480kKz7l2XYD1Pn2 | {'input_tokens': 921, 'output_tokens': 57} |
| heldout | EQ-H11 | 3 | signals | 2026-10-29T15:44:16.529628+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288655-xZekzUZANtD4qMNPUig2 | {'input_tokens': 895, 'output_tokens': 42} |
| heldout | EQ-H12 | 3 | signals | 2026-10-29T15:44:17.281814+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288656-jUF8wCllTUfACKLMYIji | {'input_tokens': 880, 'output_tokens': 42} |
| heldout | EQ-H12 | 3 | j2 | 2026-10-29T15:44:18.001885+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288657-nfLL05e9HvYNezc5LDXJ | {'input_tokens': 906, 'output_tokens': 57} |
| heldout | EQ-H13 | 3 | j2 | 2026-10-29T15:44:18.741843+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288658-wKVkhkEniMwmeWBpOnPl | {'input_tokens': 1065, 'output_tokens': 58} |
| heldout | EQ-H13 | 3 | signals | 2026-10-29T15:44:19.560420+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288658-kKgkhVgbSpFU4SKYL1QF | {'input_tokens': 1185, 'output_tokens': 42} |
| heldout | EQ-H14 | 3 | signals | 2026-10-29T15:44:20.348629+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288659-G8bNkx1CMivNWXkR08Ap | {'input_tokens': 1190, 'output_tokens': 42} |
| heldout | EQ-H14 | 3 | j2 | 2026-10-29T15:44:21.168526+00:00 | 200 | typesafe/jev-1.14-20261014 | gen-dec-1793288660-eWU2YDwwv0NuzBSukkGC | {'input_tokens': 1070, 'output_tokens': 58} |

## Architecture recommendation: five questions

1. **Noul beyond J2:** held-out catches relative to frozen hypotheses: 0 trial(s), cases []; incremental legitimate holds: 0. A catch is a request to hold/review, not verification or semantic relabelling.

2. **Score beyond J2:** held-out catches: 0 trial(s), cases []; incremental legitimate holds: 0.

3. **Score beyond Noul:** D catches beyond B: 0, cases []; extra legitimate holds: 0. Shared holds: 0; both miss the same false support: 0. A zero incremental catch provides no evidence to retain Score on top of Noul.

4. **Provisional V1 choice: A.** This recommendation uses an explicitly conservative screen: fewer held-out false continues with no increase in legitimate holds, preferring fewer judgments. If no supplemental configuration meets it, retain A and document unresolved false support rather than assume added complexity helps. This is post-evaluation architecture assessment, not threshold tuning or proof of production accuracy.

5. **Before FastAPI integration:** obtain independent labels and broader policy-edge cases, set operational review/error tolerance, validate confidence calibration separately if needed, and inspect provider failure and clarification handling. No workflow or external truth verification was tested.

## Limitations and reproducibility

The development baseline and its known error were already observed before designing these supplemental questions; development improvements are exploratory and may overfit. The 20 new scenarios are manually authored by the same experimenter and frozen before inference, not an external blind benchmark. Policy interpretation of social events and mixed uses can be debatable; frozen hypotheses remain unchanged. Three repeats are correlated measurements, not 156 independent purchases. Model/cache effects and shared evidence correlate judgments. Pairing trial IDs for historical J2 and newly collected signals is a bookkeeping comparison of the same state, not simultaneous sampling or a causal intervention. Routing can catch a prediction relative to a hypothesis or ask for information; it does not correct financial eligibility or verify underlying employee behavior. No probability is claimed calibrated.

Run `experiment_j3_j4.py` to collect; `--prepare-only` freezes with no model calls; `--report-only` regenerates artifacts with no calls. A completed run is never repeated automatically. Original J1/J2 policies, expectations and raw files are read-only inputs. New held-out labels/rules are not adjusted after inference. A future changed hypothesis requires a new separately identified experiment, not relabelling this set.

References: [official Score behavior](https://docs.typesafe.ai/primitives/score), [mixed question types](https://docs.typesafe.ai/api/system-one), [SDK question schema](https://docs.typesafe.ai/sdk/python/api/types/questions). Runtime schema/signature evidence is preserved in preregistered.json.
