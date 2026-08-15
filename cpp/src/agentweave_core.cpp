#include "agentweave_core.hpp"
#include <algorithm>

namespace agentweave {

double score_candidate(const Candidate& c) {
  return 0.42*c.coverage + 0.22*c.proficiency + 0.12*c.validated_ratio + 0.16*c.trust + 0.08*c.domain_fit;
}

std::vector<Candidate> rank_candidates(std::vector<Candidate> candidates) {
  std::sort(candidates.begin(), candidates.end(), [](const Candidate& a, const Candidate& b) {
    return score_candidate(a) > score_candidate(b);
  });
  return candidates;
}

} // namespace agentweave
