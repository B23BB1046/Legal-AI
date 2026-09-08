"""Courtroom simulation service for educational legal issue exploration."""

from __future__ import annotations

from typing import Any

from agents.core import LegalLLM, parse_json


class CourtroomSimulator:
    """Simulate court hearings and transcribe audio for educational purposes."""

    def __init__(self, llm: LegalLLM | None = None) -> None:
        self.llm = llm or LegalLLM()

    def simulate(self, question: str, facts: str = "", language: str = "English") -> dict[str, Any]:
        """Simulate a courtroom hearing for a given question and optional facts."""
        question = question.strip()
        facts = facts.strip()
        if not question:
            raise ValueError("question must not be empty")
        if language not in {"English", "Hindi"}:
            raise ValueError("language must be English or Hindi")
            
        language_instruction = (
            "Respond in simple Hindi using short sentences and explain legal terms."
            if language == "Hindi"
            else "Respond in simple English using short sentences and explain legal terms."
        )
        
        prompt = f"""You are simulating a courtroom hearing for an ordinary person.
Use simple everyday language, short sentences, and explain every legal term the first time it appears.
{language_instruction}
Do not provide legal advice or invent authorities. Use only the issue and facts supplied.
Issue: {question}
Facts: {facts or 'No additional facts supplied.'}
Return only JSON with these string fields: petitioner, respondent, judge, outcome.
Each role should be concise, identify uncertainty, and avoid claiming that the simulation is a real court order."""

        try:
            response = self.llm.generate(prompt)
            result = parse_json(response, {})
            if all(result.get(key) for key in ("petitioner", "respondent", "judge", "outcome")):
                return {
                    "question": question,
                    "facts": facts,
                    "language": language,
                    **result,
                    "disclaimer": self.disclaimer,
                }
        except Exception:
            pass
            
        return self._offline_simulation(question, facts, language)

    def transcribe(self, audio: bytes, filename: str = "recording.wav") -> str:
        """Transcribe microphone audio with Groq Whisper."""
        if not audio:
            raise ValueError("audio must not be empty")
            
        response = self.llm.client.audio.transcriptions.create(
            file=(filename, audio),
            model="whisper-large-v3-turbo",
            response_format="json",
        )
        transcript = getattr(response, "text", "") or ""
        if not transcript.strip():
            raise RuntimeError("Speech transcription returned no text.")
        return transcript.strip()

    def simulate_voice(
        self,
        audio: bytes,
        filename: str = "recording.wav",
        facts: str = "",
        language: str = "English",
    ) -> dict[str, Any]:
        """Transcribe a voice question and run the courtroom simulation."""
        transcript = self.transcribe(audio, filename)
        result = self.simulate(transcript, facts, language)
        result["transcript"] = transcript
        return result

    def judge_hearing(
        self,
        petitioner: str,
        respondent: str,
        facts: str = "",
        language: str = "English",
    ) -> dict[str, Any]:
        """Evaluate separately transcribed petitioner and respondent statements."""
        petitioner = petitioner.strip()
        respondent = respondent.strip()
        facts = facts.strip()
        if not petitioner or not respondent:
            raise ValueError("Both petitioner and respondent statements are required")
        if language not in {"English", "Hindi"}:
            raise ValueError("language must be English or Hindi")
            
        language_instruction = (
            "Respond in simple Hindi using short sentences and explain legal terms."
            if language == "Hindi"
            else "Respond in simple English using short sentences and explain legal terms."
        )
        
        prompt = f"""You are a neutral judge in an educational courtroom role-play.
{language_instruction}
Consider both statements fairly. Do not invent facts or authorities and do not issue real legal advice.
Petitioner statement: {petitioner}
Respondent statement: {respondent}
Additional facts: {facts or 'No additional facts supplied.'}
Return only JSON with string fields judge and outcome.
The judge field must explain the key issue and uncertainty. The outcome must explain what evidence or next steps a real court would need."""

        try:
            result = parse_json(self.llm.generate(prompt), {})
            if result.get("judge") and result.get("outcome"):
                return {
                    "petitioner": petitioner,
                    "respondent": respondent,
                    "judge": result["judge"],
                    "outcome": result["outcome"],
                    "language": language,
                    "disclaimer": self.disclaimer,
                }
        except Exception:
            pass
            
        return self._offline_hearing(petitioner, respondent, facts, language)

    @property
    def disclaimer(self) -> str:
        """Return the required educational disclaimer."""
        return "Educational simulation only; not legal advice or a court order. Verify authorities with a qualified lawyer."

    def _offline_simulation(self, question: str, facts: str, language: str = "English") -> dict[str, Any]:
        """Provide fallback responses when LLM generation fails for full simulation."""
        if language == "Hindi":
            return {
                "question": question,
                "facts": facts,
                "language": language,
                "petitioner": f"याचिकाकर्ता कहता है कि अदालत को मदद करनी चाहिए क्योंकि समस्या है: {question}।",
                "respondent": "दूसरा पक्ष कहता है कि अदालत को सबूत और लागू कानून देखकर ही फैसला करना चाहिए।",
                "judge": "जज पूछेंगे कि क्या हुआ, कौन से सबूत हैं और कौन सा कानून लागू होता है। कठिन शब्दों को सरल भाषा में समझाया जाएगा।",
                "outcome": "इस अभ्यास में कोई वास्तविक फैसला नहीं दिया गया है। असली अदालत को पूरे तथ्य और दस्तावेज चाहिए।",
                "disclaimer": self.disclaimer,
            }
        return {
            "question": question,
            "facts": facts,
            "language": language,
            "petitioner": f"The petitioner says: the court should help because the problem is about {question}. They would explain how the facts have affected them.",
            "respondent": "The respondent gives the other side of the story and says the court should check the evidence and apply the correct legal rule before granting relief.",
            "judge": "The judge would ask what happened, what proof is available, and which law applies. The judge would explain difficult legal words in simple language.",
            "outcome": "No decision is made in this practice hearing. A real court would need the complete facts, documents, and arguments.",
            "disclaimer": self.disclaimer,
        }

    def _offline_hearing(
        self, petitioner: str, respondent: str, facts: str, language: str
    ) -> dict[str, Any]:
        """Provide fallback responses when LLM generation fails for judge hearings."""
        if language == "Hindi":
            judge = "जज दोनों पक्षों की बात और उपलब्ध सबूत देखेंगे। अभी पूरी जानकारी के बिना अंतिम निर्णय नहीं दिया जा सकता।"
            outcome = "असली अदालत में दस्तावेज, गवाह और लागू कानून की जांच जरूरी होगी। यह केवल अभ्यास है।"
        else:
            judge = "The judge would consider both statements and the available evidence. A final decision cannot be made without the complete record."
            outcome = "A real court would need to examine documents, witnesses, and the applicable law. This is only a practice hearing."
            
        return {
            "petitioner": petitioner,
            "respondent": respondent,
            "judge": judge,
            "outcome": outcome,
            "facts": facts,
            "language": language,
            "disclaimer": self.disclaimer,
        }