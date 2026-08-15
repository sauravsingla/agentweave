#pragma once
#include <string>
#include <vector>
#include <unordered_set>

namespace agentweave {
struct Candidate {
  std::string id;
  std::vector<std::string> capabilities;
  double proficiency{0.5};
  double trust{0.5};
  double placement{0.5};
};
struct Ranked { std::string id; double score; std::vector<std::string> matched; };
std::vector<Ranked> rank(const std::vector<std::string>& required,const std::vector<Candidate>& candidates);
std::vector<std::string> select_team(const std::vector<std::string>& required,const std::vector<Ranked>& ranked,std::size_t max_agents=5);
}
