# Prompting techniques: what each does and when to use it

Summarised in our own words from *The Prompt Report* (Schulhoff et al., 2024, arXiv:2406.06608, CC BY 4.0), which
reviewed 1,565 papers and catalogued 58 text prompting techniques. Each line names the technique, what it does, and
when it tends to help. Treat reported gains as hints to test, not guarantees: the survey itself warns that results
often do not transfer to other models or datasets.

## Contents

- [Few-shot design decisions](#few-shot-design-decisions)
- [Zero-shot techniques](#zero-shot-techniques)
- [Thought generation (chain-of-thought)](#thought-generation)
- [Decomposition](#decomposition)
- [Ensembling](#ensembling)
- [Self-criticism](#self-criticism)
- [Answer engineering](#answer-engineering)
- [Automatic prompt optimisation](#automatic-prompt-optimisation)
- [Prompt sensitivity and alignment issues](#prompt-sensitivity-and-alignment)
- [Multilingual and multimodal prompts](#multilingual-and-multimodal)
- [Agents, tools and retrieval](#agents-tools-and-retrieval)
- [What the case studies showed](#what-the-case-studies-showed)
- [Vocabulary](#vocabulary)

## Few-shot design decisions

Six choices about exemplars change results, sometimes from under 50% to over 90% accuracy:

1. **Quantity**: more exemplars usually help, especially for large models; gains often flatten after about 20.
   Long-context models can keep improving with more.
2. **Order**: order alone can swing accuracy widely. Shuffle; when it matters, try several orders and ensemble.
3. **Label distribution**: unbalanced labels bias the model toward the majority label. Balance them.
4. **Label quality**: wrong labels sometimes hurt little, sometimes a lot (small models suffer more). If exemplars
   come from a noisy dataset, check them.
5. **Format**: one consistent format, ideally one common in training data ("Q: ... A: ...", "Input/Output").
   Try two or three formats on the dev set.
6. **Similarity**: exemplars similar to the input usually help; sometimes diverse ones help more. Test both.

Instructions before exemplars matter less than expected for correctness (generic "Complete the task" can do as well
as a specific one), but still steer style and format.

Exemplar selection methods: **kNN** (pick nearest training examples per input; costs a retrieval step), **Vote-K**
(have a model propose diverse unlabeled candidates for a human to label), **SG-ICL** (the model writes its own
exemplars; better than nothing, worse than real data), **Prompt mining** (prefer phrasings frequent in large
corpora).

## Zero-shot techniques

- **Role / persona**: "You are a travel writer". Helps open-ended writing and tone; occasional accuracy gains.
- **Style**: state the tone, genre or length.
- **Emotion**: add stakes ("This is important to my career"); reported gains on some benchmarks.
- **System 2 Attention (S2A)**: first ask the model to rewrite the prompt without irrelevant details, then answer the
  cleaned prompt. Use when inputs contain distracting or leading text.
- **SimToM**: for questions about what different people know, first list the facts one person knows, then answer
  from those only.
- **Rephrase and Respond (RaR)**: "Rephrase and expand the question, and respond." Helps underspecified questions.
- **Re-reading (RE2)**: repeat the question ("Read the question again: ...").
- **Self-Ask**: let the model decide whether it needs follow-up questions, answer them, then answer the original.

## Thought generation

- **Chain-of-thought (CoT)**: exemplars that show reasoning before the answer. Large gains on maths and logic.
- **Zero-shot CoT**: append a thought inducer: "Let's think step by step." Variants: "Let's work this out in a step
  by step way to be sure we have the right answer"; **Plan-and-Solve**: "Let's first understand the problem and
  devise a plan to solve it. Then, let's carry out the plan and solve the problem step by step"; **Thread-of-Thought**
  for long contexts: "Walk me through this context in manageable parts step by step, summarizing and analyzing as we
  go."
- **Step-Back**: first ask a general question about the underlying concept or principle, then reason.
- **Analogical**: the model generates its own related solved examples with reasoning, then solves the task.
- **Tabular CoT**: reason as a Markdown table (columns such as step, sub-question, process, result).
- **Contrastive CoT**: include both a correct and an incorrect reasoning exemplar, labelled, to show what to avoid.
- **Complexity-based**: choose exemplars with long reasoning; at inference sample several chains and vote among the
  longer ones.
- **Auto-CoT**: generate CoT exemplars automatically with zero-shot CoT, then use them few-shot.
- **Active prompting**: find training questions where the model's samples disagree most, have humans write reasoning
  for those.
- **Uncertainty-routed CoT**: sample several chains; take the majority if agreement passes a threshold, else fall
  back to the greedy answer.

## Decomposition

- **Least-to-Most**: ask for the sub-problems first (without solving), then solve them in order, feeding each answer
  forward. Good for compositional and symbolic tasks.
- **DECOMP**: show the model how to call helper functions (split text, search, another prompt) and let it route
  sub-problems to them.
- **Plan-and-Solve**: the zero-shot wording above.
- **Tree-of-Thought**: branch several candidate next steps, score progress, expand the promising ones. For search and
  planning tasks; costs many calls.
- **Recursion-of-Thought**: send a hard sub-problem to a separate call and paste back the answer; helps when the full
  reasoning would not fit in context.
- **Program-of-Thoughts / Faithful CoT**: write code (or another formal language) as the reasoning and execute it.
  Strong for arithmetic and programming; weaker for semantic reasoning.
- **Skeleton-of-Thought**: draft an outline, expand each point in parallel calls, join. Cuts latency.
- **Metacognitive**: a five-step chain: clarify the question, preliminary judgement, evaluate it, confirm, state
  confidence.

## Ensembling

Run several prompts or samples and aggregate. Lowers variance and often raises accuracy, at the cost of more calls.

- **Self-consistency**: sample several CoT answers at non-zero temperature (about 0.5-0.7) and take the majority.
- **Universal self-consistency**: for free-form text, put all candidates in one prompt and ask which answer is most
  common.
- **Demonstration ensembling (DENSE)**: several few-shot prompts with different exemplar subsets; aggregate.
- **Mixture of reasoning experts (MoRE)**: different specialised prompts (retrieval for facts, CoT for maths) and
  pick by agreement.
- **Prompt paraphrasing**: reword the prompt to make ensemble members.
- **Meta-reasoning over multiple CoTs, DiVeRSe, COSP, USP, Max Mutual Information**: variants that score or merge
  reasoning chains, or build exemplars from high-agreement outputs.

## Self-criticism

- **Self-Calibration**: after answering, ask "Is this answer correct?" to estimate confidence.
- **Self-Refine**: feedback on the answer, then a rewrite using the feedback; repeat until good enough or N rounds.
- **Chain-of-Verification (CoVe)**: draft; list questions that would verify it; answer each independently; revise.
- **Self-Verification**: produce candidates, mask part of the question, and check which candidate lets the model
  recover it.
- **Reversing CoT**: reconstruct the problem from the answer and compare it with the original to find mistakes.
- **Cumulative reasoning**: propose steps, accept or reject each, repeat until solved.

## Answer engineering

Three decisions, made together with the prompt:

- **Answer shape**: a token, a span, a JSON object. Restrict to one token for classification when possible.
- **Answer space**: the allowed values (e.g. two labels). Say them in the prompt.
- **Extractor**: how the final answer is read. A **verbalizer** maps outputs to labels ("+" means positive). A
  **regex** finds the label; after reasoning, search for the *last* occurrence. A separate **LLM extractor** with an
  answer trigger ("The answer (Yes or No) is") handles messy output, but can hide errors: in the case study, adding an
  extraction prompt raised accuracy while lowering F1, because many unparsed outputs were also wrong.

Output formatting (JSON, XML, CSV) can lower accuracy on some tasks and raise it on others: measure.

## Automatic prompt optimisation

- **Meta prompting**: "Improve the following prompt: {PROMPT}". Cheap first step; no scoring.
- **APE**: generate many candidate instructions from exemplars, score on data, paraphrase the best, repeat.
- **GrIPS**: edit operations (delete, add, swap, paraphrase) on a starting prompt, keep improvements.
- **ProTeGi**: run a batch, ask a model to criticise the prompt from the errors ("textual gradients"), generate
  revisions, pick with a bandit.
- **DSPy**: optimises exemplars and instructions for a metric. In the survey's case study it reached test F1 0.548 and beat
  the prompts from 20 hours of expert manual work on the test set; combining automation with human revision worked
  best.

## Prompt sensitivity and alignment

- **Small changes, big effects**: extra spaces, capitalisation, delimiters, synonyms, option order. One study saw a
  7B model's score range from near 0 to 0.80 across formats. Keep the format fixed once tuned.
- **Task format**: "Classify as positive or negative" vs "Is this review positive?" changed GPT-3 accuracy by up to 30%.
- **Prompt drift**: a hosted model update changes behaviour. Re-run your dev set after model changes.
- **Overconfidence**: models are overconfident when asked to state confidence in words ("1 to 10"); don't rely on it.
- **Sycophancy**: models agree with opinions stated in the prompt and flip answers under pushback ("Are you sure?",
  "I'm confident you are wrong"), more so for large instruction-tuned models. Keep opinions and false assumptions out.
  Even "Detect all instances where the input is harmful" presupposes harm.
- **Bias**: an instruction to be unbiased, balanced exemplars, and **AttrPrompt** for synthetic data (list attributes
  to vary, such as location or length, then generate across them).
- **Ambiguity**: let the model ask clarifying questions first; or include exemplars with ambiguous labels.

## Multilingual and multimodal

- English prompt templates often work better than task-language templates, even for non-English tasks; human
  translation beats machine translation when a native template is needed. Test both.
- **Translate first**: translate input to English, then prompt.
- Choose semantically similar exemplars; for translation, **Chain-of-Dictionary** (add dictionary meanings of key
  words) and **DecoMT** (translate chunks, then combine) help.
- Images: **prompt modifiers** (medium, lighting), **negative prompts** (down-weight "extra fingers"), paired
  before/after images as exemplars, describe an image as text to reuse text techniques, multimodal CoT ("Solve this
  step by step" with an image).

## Agents, tools and retrieval

- An agent is a model that serves the user's goal through actions outside itself (calculator, code, search, APIs).
- **MRKL**: a router model that picks tools. **CRITIC**: draft, critique, then verify with tools (search, code).
- **PAL / ToRA**: write code for the reasoning and run it; ToRA interleaves code and reasoning.
- **ReAct**: thought, action, observation, repeated, all kept in the prompt. **Reflexion** adds a written reflection
  on failures to the next attempt.
- **RAG**: retrieve text and put it in the prompt; **IRCoT** interleaves retrieval with reasoning; **FLARE** drafts
  the next sentence and uses it as the search query.
- LLM-as-evaluator: give a role, criteria definitions, exemplars and CoT; ask for a score per item (pairwise
  comparison is order-sensitive); JSON or XML output helps; batching many items in one prompt often hurts. See
  `llm-evals`.

## What the case studies showed

- **MMLU (2,800 questions, gpt-3.5-turbo)**: zero-shot 0.627, zero-shot CoT 0.547 (0.574 with
  self-consistency), few-shot 0.652, few-shot CoT 0.692 (0.691 with self-consistency). More complex was usually, not always, better.
- **Labeling a sensitive construct (entrapment in suicide-risk posts)**: 47 steps, about 20 hours, from 0 (no
  parsable output) to F1 0.53. Lessons: the model may refuse or give advice instead of labelling (switching model
  fixed it); answer extraction choices moved scores; an accidental duplicated paragraph helped and removing it hurt,
  so effects can be inexplicable; an instruction that raised F1 ("only label explicit statements") contradicted the
  domain experts' real goal (recall matters most). Talk to the domain expert, and keep a held-out test set.

## Vocabulary

- **Prompt**: the full input to the model. **Prompt template**: a prompt with variables ({TWEET}) filled per input.
- **Directive**: the instruction or question. **Exemplar / shot**: a worked example.
- **In-context learning**: the model picks up a task from exemplars or instructions in the prompt, without weight
  updates (often it already knew the task).
- **Thought inducer**: a phrase that triggers step-by-step reasoning. **Answer trigger**: a phrase that elicits the
  final answer ("Therefore, the answer is").
- **Prompt chain**: two or more templates where one's output fills the next. **Verbalizer / extractor**: map output to
  labels.
- **Prompt engineering**: iterating on a prompt against a score. **Answer engineering**: designing answer shape,
  space and extractor.
