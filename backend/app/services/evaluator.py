from sacrebleu.metrics import BLEU, CHRF


class EvaluatorService:
    def __init__(self) -> None:
        self.bleu = BLEU(effective_order=True)
        self.chrf = CHRF(word_order=2)

    def evaluate(self, candidate: str, reference: str) -> tuple[float, float]:
        bleu_score = self.bleu.sentence_score(candidate, [reference]).score
        chrf_score = self.chrf.sentence_score(candidate, [reference]).score
        return round(bleu_score, 3), round(chrf_score, 3)

