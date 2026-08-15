#include "agentweave_core.hpp"
#include <algorithm>
#include <unordered_map>

namespace agentweave {
std::vector<Ranked> rank(const std::vector<std::string>& required,const std::vector<Candidate>& candidates){
  std::unordered_set<std::string> need(required.begin(),required.end());
  std::vector<Ranked> out; out.reserve(candidates.size());
  for(const auto& c:candidates){
    std::vector<std::string> matched;
    for(const auto& cap:c.capabilities) if(need.count(cap)) matched.push_back(cap);
    const double coverage=need.empty()?1.0:static_cast<double>(matched.size())/need.size();
    const double score=.50*coverage+.20*c.proficiency+.20*c.trust+.10*c.placement;
    out.push_back({c.id,score,matched});
  }
  std::sort(out.begin(),out.end(),[](const Ranked&a,const Ranked&b){return a.score>b.score;});
  return out;
}
std::vector<std::string> select_team(const std::vector<std::string>& required,const std::vector<Ranked>& ranked,std::size_t max_agents){
  std::unordered_set<std::string> uncovered(required.begin(),required.end());
  std::vector<std::string> team; std::unordered_set<std::string> used;
  while(!uncovered.empty() && team.size()<max_agents){
    const Ranked* best=nullptr; std::size_t gain=0;
    for(const auto& r:ranked){
      if(used.count(r.id)) continue;
      std::size_t g=0; for(const auto& c:r.matched) if(uncovered.count(c)) ++g;
      if(g>gain || (g==gain && g>0 && (!best || r.score>best->score))){best=&r;gain=g;}
    }
    if(!best||gain==0) break;
    team.push_back(best->id); used.insert(best->id); for(const auto& c:best->matched) uncovered.erase(c);
  }
  if(team.empty()&&!ranked.empty()) team.push_back(ranked.front().id);
  return team;
}
}
