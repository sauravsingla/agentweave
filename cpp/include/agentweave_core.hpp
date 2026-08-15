#pragma once
#include <string>
#include <vector>

namespace agentweave {

struct Candidate {
  std::string id;
  double coverage{0.0};
  double proficiency{0.0};
  double validated_ratio{0.0};
  double trust{0.0};
  double domain_fit{0.0};
};

double score_candidate(const Candidate& c);
std::vector<Candidate> rank_candidates(std::vector<Candidate> candidates);

} // namespace agentweave
