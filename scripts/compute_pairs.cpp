// All-pair Pearson correlation and overlap counts. MI is computed separately by JIDT.
// Build: g++ -O3 -std=c++17 -fopenmp scripts/compute_pairs.cpp -o work/compute_pairs
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _OPENMP
#include <omp.h>
#endif

template<class T> std::vector<T> read_array(const std::string& name, size_t n) {
    std::vector<T> out(n);
    std::ifstream f(name, std::ios::binary | std::ios::ate);
    if (!f || f.tellg() != std::streamoff(n * sizeof(T)))
        throw std::runtime_error("Wrong byte length for " + name);
    f.seekg(0);
    if (!f.read(reinterpret_cast<char*>(out.data()), n * sizeof(T)))
        throw std::runtime_error("Cannot read " + name);
    return out;
}
template<class T> void write_array(const std::string& name, const std::vector<T>& a) {
    std::ofstream f(name, std::ios::binary);
    f.write(reinterpret_cast<const char*>(a.data()), a.size() * sizeof(T));
    if (!f) throw std::runtime_error("Cannot write " + name);
}
int main(int argc, char** argv) {
  try {
    if (argc != 7) throw std::runtime_error("Usage: compute_pairs WORK N T MIN_OVERLAP BINS THREADS");
    const std::string dir = argv[1];
    const int N = std::stoi(argv[2]), T = std::stoi(argv[3]);
    const int minimum = std::stoi(argv[4]), B = std::stoi(argv[5]), threads = std::stoi(argv[6]);
    if (N < 2 || T < 2 || T > 65535 || B < 2 || B > 32 || minimum < 2)
        throw std::runtime_error("Invalid dimensions or settings");
#ifdef _OPENMP
    omp_set_num_threads(std::max(1, threads));
#endif
    auto data = read_array<double>(dir + "/centered.bin", size_t(N)*T);
    auto bins = read_array<int8_t>(dir + "/bins.bin", size_t(N)*T);
    for (size_t p=0; p<bins.size(); ++p) {
        if (bins[p] < -1 || bins[p] >= B)
            throw std::runtime_error("Bin code outside -1 or 0..B-1");
        if (bins[p] >= 0 && !std::isfinite(data[p]))
            throw std::runtime_error("Observed bin has a nonfinite reading");
    }
    const size_t P = size_t(N)*(N-1)/2;
    const float nan = std::numeric_limits<float>::quiet_NaN();
    std::vector<float> corr(P, nan);
    std::vector<uint16_t> counts(P, 0);
    // Each iteration owns one contiguous part of the upper triangle.
#pragma omp parallel for schedule(dynamic, 4)
    for (int i = 0; i < N-1; ++i) {
        const double* x = data.data()+size_t(i)*T;
        const int8_t* xb = bins.data()+size_t(i)*T;
        size_t k = size_t(i)*(2*size_t(N)-i-1)/2;
        for (int j=i+1; j<N; ++j, ++k) {
            const double* y = data.data()+size_t(j)*T;
            const int8_t* yb = bins.data()+size_t(j)*T;
            int n=0;
            double sx=0, sy=0, xx=0, yy=0, xy=0, origin_x=0, origin_y=0;
            bool variable_x=false, variable_y=false;
            for (int t=0; t<T; ++t) {
                const int a=xb[t], b=yb[t];
                if (a < 0 || b < 0) continue;
                if (n == 0) { origin_x=x[t]; origin_y=y[t]; }
                const double dx=x[t]-origin_x, dy=y[t]-origin_y;
                variable_x = variable_x || dx != 0;
                variable_y = variable_y || dy != 0;
                ++n;
                sx+=dx; sy+=dy;
                xx+=dx*dx; yy+=dy*dy; xy+=dx*dy;
            }
            counts[k]=uint16_t(n);
            if (n < minimum) continue;
            const double vx=xx-sx*sx/n, vy=yy-sy*sy/n;
            if (variable_x && variable_y && vx > 0 && vy > 0)
                corr[k]=float(std::clamp((xy-sx*sy/n)/std::sqrt(vx*vy), -1.0, 1.0));
        }
    }
    write_array(dir+"/correlation.bin",corr);
    write_array(dir+"/overlap.bin",counts);
    std::cout << "Computed Pearson and overlap for " << P << " pairs" << std::endl;
  } catch(const std::exception& e) {
    std::cerr << e.what() << std::endl; return 1;
  }
}
