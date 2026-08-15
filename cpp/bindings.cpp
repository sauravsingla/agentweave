#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "agentweave_core.hpp"
namespace py=pybind11;
PYBIND11_MODULE(_agentweave_core,m){
  py::class_<agentweave::Candidate>(m,"Candidate")
    .def(py::init<>())
    .def_readwrite("id",&agentweave::Candidate::id)
    .def_readwrite("capabilities",&agentweave::Candidate::capabilities)
    .def_readwrite("proficiency",&agentweave::Candidate::proficiency)
    .def_readwrite("trust",&agentweave::Candidate::trust)
    .def_readwrite("placement",&agentweave::Candidate::placement);
  py::class_<agentweave::Ranked>(m,"Ranked")
    .def_readonly("id",&agentweave::Ranked::id)
    .def_readonly("score",&agentweave::Ranked::score)
    .def_readonly("matched",&agentweave::Ranked::matched);
  m.def("rank",&agentweave::rank);
  m.def("select_team",&agentweave::select_team,py::arg("required"),py::arg("ranked"),py::arg("max_agents")=5);
}
