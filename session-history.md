I provided you with two links.

The first one is for a brand-new NVIDIA transcription model. It's their latest and most powerful voice-to-text model. But that's not all: it can also perform additional operations on the transcribed text, which is what really caught my attention.

My only concern with this model is that it's very large, and I believe it also requires relatively powerful hardware to run.

You can look up my computer's hardware specifications. I have an RTX 5060 with 8 GB of VRAM, 16 GB of DDR5 RAM, and a Ryzen 7 600-series processor. My hardware is fairly average, with moderate specifications rather than particularly high-end capabilities.

What I want you to do is research this model online and investigate what the community is saying about it. Specifically, I want you to find out whether there's an ONNX Runtime version available, whether there's another quantized version, or whether we can use modern quantization techniques to make it more efficient.

If you're not familiar with the latest quantization techniques, I also want you to research those. There are now some advanced techniques that can significantly compress models while retaining almost the same quality. For example, a model might be compressed by 10x while maintaining the same quality, or perhaps 90% of its original quality, which would still be a good result.

One example is TurboQuant, but there are obviously other quantization techniques as well that I want you to investigate.

What I particularly like about this NVIDIA model is that it supports multiple languages, which would be extremely useful for our application because our application already supports multiple languages.

Another feature that caught my attention is its ability to perform operations on dictations.

For example, imagine that I record a ten-minute dictation and the model converts the voice to text exactly as spoken. I might then want the resulting dictation to be more formal, or I might want it corrected so that it contains no spelling mistakes, grammar errors, or punctuation issues.

We already have some checks for punctuation and grammar in our application, but we're currently handling them using basic algorithms. Naturally, these algorithms won't always be 100% accurate.

For example, we already have automatic punctuation in the application, but we don't really have proper grammar correction. We only have basic grammar handling.

There are also other operations, such as text polishing, where the model improves the text. For example, I might dictate something for just one minute, and then ask the model to expand that dictation by adding relevant information related to what I said, even if I didn't explicitly mention those details.

Other operations could include expanding the text, shortening it, cleaning it up, and improving its structure.

These are exactly the kinds of operations I'm interested in. Instead of dictating something, sending it to ChatGPT online, asking ChatGPT to process it, waiting for the response, copying the result, and then using it, I want the application to produce the text in the form I actually want from the beginning.

That's the idea I'm considering.

We already have a plan or ADR for this functionality, but we haven't fully implemented it yet. We're still in the planning and research stage because we're looking for suitable models that can handle these requirements.

You can also look through our documentation folder. You'll find documents describing this functionality and what we're trying to achieve with it. We're essentially researching models that can support all these use cases.

Initially, my plan was to use one model for transcription, such as Whisper, and then use a second, smaller model whose only responsibility would be processing the resulting dictation. It would be responsible for expanding, shortening, cleaning up, and correcting the grammar of the text.

Obviously, that would require a second model.

What I find particularly interesting about this new NVIDIA model is that it combines both capabilities into one model. It can perform transcription and also accept instructions to perform operations on the resulting dictation.

That's a significant advantage.

Another thing that particularly attracted me to this model is its claimed support for Arabic.

Arabic is actually the language I use most frequently for dictation.

For context, the message you're reading right now was originally dictated in Arabic. I then used ChatGPT to convert it from Arabic into English, which is why you're reading it in English.

In reality, I dictated the entire message in Arabic using ChatGPT's voice-to-text feature.

My workflow is currently as follows:

1. I dictate a message in Arabic, sometimes mixing Arabic and English technical terms.
2. ChatGPT receives the mixed Arabic-English dictation.
3. ChatGPT converts it into English.
4. I copy the English result and use it wherever I need it.

This is exactly the workflow I'm trying to eliminate.

I noticed that NVIDIA claims its model supports Arabic. Of course, it might not be particularly good at Arabic, but that's something we need to test if we decide to use it.

However, there's an important distinction regarding Arabic support.

I'm not talking about Modern Standard Arabic or formal Arabic. Arabic has several variations and dialects, including Egyptian Arabic, Saudi Arabic, and Modern Standard Arabic, among others.

The dialect I primarily use is Egyptian Arabic. That's my native language, and it's what I use most frequently when speaking.

If you want to understand the kind of Arabic-English dictation I typically produce, I've provided a file called Dictation examples. It contains several examples of how I normally dictate messages.

I want us to find a model that can handle this particular type of dictation.

Ideally, I want to give the model audio in the same format as my examples and have it produce the corresponding text accurately.

It doesn't necessarily need to translate everything into English. In fact, I don't want to introduce that functionality immediately.

Let's start with the first level:

The model should transcribe the audio exactly as spoken, preserving the original languages and wording.

If I dictate in a mixture of Arabic and English, it should produce the same Arabic-English mixture.

It should preserve the same language, the same text, and exactly what I intended to say, without translating or rewriting anything.

This is the first level of functionality we need.

Later, as a second stage, we can explore how to automate the process so that the output is entirely in English. But that's something for the future.

For now, the priority is to reproduce the original mixed Arabic-English dictation accurately, following the same style and structure shown in the examples I provided.

The second link is for a text-to-speech model.

This model takes text and converts it into speech.

What makes this model interesting is that it could allow us to evolve our application from being purely a dictation application into something more.

We could retain the existing dictation functionality while introducing another optional feature that users can enable or disable.

Alternatively, users could use both features together.

The idea is to allow users not only to dictate text into the application but also to have actual spoken conversations with it.

Instead of the application simply receiving the user's speech and returning text, it could also respond to the user with spoken audio.

For example, we could have two separate hotkeys:

- One dedicated hotkey for dictation.
- Another dedicated hotkey for interacting with the application as an assistant.

This would allow users to choose whether they want to dictate something or have a conversation with the application.

I think this could be a really useful addition.

We already have this functionality documented as well. We previously created a plan for it, but we haven't fully implemented it because the models we evaluated previously didn't meet our requirements.

Some models were too small or incapable of handling conversations properly. Others sounded robotic and didn't feel human enough. Some models were also excessively large and required more resources than we could reasonably allocate.

I came across this new model, and its size is approximately 2.5 GB, with around 500 million parameters.

That sounds promising because I believe I could run it locally on my computer without requiring excessive resources.

I think it's worth investigating.

We already have a proposed architecture for this functionality, although I'm not sure whether it's the right approach or whether there's a better alternative.

The architecture I'm currently considering is:

1. The application uses its dictation model to convert the user's speech into text.
2. That text is then passed to the second model, which is actually the text-to-speech model.
3. The second model takes the text and generates a spoken response instead of returning a text response.

This could be a powerful feature. It would make the application feel more interactive and alive, rather than being a silent application that only receives speech and produces text.

The application could actually respond to the user.

I want you to research this second model as well and evaluate its capabilities, performance, and suitability for our application.

An extremely important requirement for both models is compatibility with our existing application architecture and backend.

I want you to investigate how we can integrate both models in a way that fits our current technology stack.

For example, we currently use ONNX Runtime. We do not use Torch or PyTorch.

Therefore, any solution we adopt must allow us to run these models through ONNX Runtime rather than requiring PyTorch.

The same principle applies to other dependencies and libraries.

If a model requires a custom backend, that's completely fine. We can implement a dedicated backend in our codebase.

However, if it requires us to replace ONNX Runtime with PyTorch or introduce PyTorch as a required dependency, that's absolutely not an option.

We cannot make that architectural change.

So, the integration approach must respect our existing technology stack.

We already have custom backends for Whisper and NVIDIA Parakeet, so implementing another dedicated backend isn't a problem.

I also understand why individual models sometimes require their own custom backends: most models have different architectures and processing requirements, so one universal backend won't necessarily work with every model.

That's perfectly understandable.


## model

AGENTS.md file has been read successfully.

Report: research-nemotron-3.5-transcribe-and-audio8-tts.md. Three findings, in order of how much they hurt.

1. The 30B does not fit your machine. Not "tight" — impossible.
Measured on this box: RTX 5060 = 8151 MiB, total RAM = 15.20 GB. Smallest published quant is AD-Q2_0_M = 13.57 GB decoder + 1.67 GB mandatory encoder = 15.24 GB of weights. That's more than your entire system RAM, before Windows takes its share. MoE offload doesn't save you — offloading experts to RAM still requires the weights to be in RAM. NVIDIA's own SALM config table starts at 24 GB. There is no quant, no flag, no split.

2. TurboQuant is not what you think it is. It's KV-cache compression (PolarQuant + QJL, ~3-bit, ~6x, Google Research, ICLR 2026) — not weight compression. It shrinks the cache, never the 34 B of weights. Wrong lever for this wall. 4-bit is 19.68 GB, 2-bit is 13.57 GB — quantization moved it 4.8x and still missed by 4 GB.

Also: no ONNX for the 30B, and that's structural — Mamba-2 + MoE + parallel expert encoder + CTC + MTP head. Sanctioned runtimes are vLLM, SGLang-Omni, Transformers, GGML. Nobody's exporting that to ORT.

3. The model you actually want already exists, one level down. nvidia/nemotron-3.5-asr-streaming-0.6b — 600M, Arabic in the TOP tier (not the 30B's bottom "Supported" tier), native punctuation, OpenMDW-1.1, 691k downloads. Community ONNX builds split encoder/decoder/joint — same shape as your Parakeet backend. And there's an Egyptian-Arabic (arz) adapter fine-tune on that exact base. ~600 MB INT8. Fits with room.

It has no instruction following — so polish/expand stays a second model. Your two-model plan was right; the 30B is the wrong way to collapse it.

Audio8 TTS: no, as specified. 2.55 GB vs ADR-0027's ≤1 GB budget, torch-only (trust_remote_code, torch≥2.5), no ONNX — and a 10-codebook autoregressive decode is the least exportable shape in speech. Arabic is uneven too: CV3 WER 21.1% vs MiniMax CER 2.4%. Same suite disagreement, order of magnitude.

One thing I couldn't verify and won't pretend to: whether MagpieTTS (the TTS inside NeMo-Speech.cpp) covers Arabic. If it does, one binary gives you ASR + TTS with no torch and no ONNX export. That's worth one focused check before anything else.
