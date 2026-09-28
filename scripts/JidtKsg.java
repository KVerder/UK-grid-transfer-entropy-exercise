import infodynamics.measures.continuous.kraskov.MutualInfoCalculatorMultiVariateKraskov1;
import infodynamics.utils.MatrixUtils;
import java.util.Random;

/** Continuous JIDT KSG algorithm 1; explicit, reproducible tie breaking. */
public final class JidtKsg {
    public static MutualInfoCalculatorMultiVariateKraskov1 calculator(int k) throws Exception {
        MutualInfoCalculatorMultiVariateKraskov1 c = new MutualInfoCalculatorMultiVariateKraskov1();
        c.setProperty("k", Integer.toString(k));
        c.setProperty("NUM_THREADS", "1"); // Parallelize pairs, not observations within a pair.
        c.setProperty("NORMALISE", "false");
        c.setProperty("NOISE_LEVEL_TO_ADD", "0");
        c.setProperty("DYN_CORR_EXCL", "0");
        c.setProperty("NORM_TYPE", "MAX_NORM");
        return c;
    }

    public static double estimate(MutualInfoCalculatorMultiVariateKraskov1 c,
                                  double[] x, double[] y, long seed, double noise) throws Exception {
        boolean variableX = false, variableY = false;
        for (int t=1; t<x.length; t++) {
            variableX |= x[t] != x[0]; variableY |= y[t] != y[0];
        }
        // Degenerate constant variables have MI zero; avoid normalizing zero variance.
        if (!variableX || !variableY) return 0.0;
        MatrixUtils.normalise(x); MatrixUtils.normalise(y);
        Random random = new Random(seed);
        for (int t=0; t<x.length; t++) {
            x[t] += noise * random.nextGaussian();
            y[t] += noise * random.nextGaussian();
        }
        c.initialise(1, 1);
        c.setObservations(x, y);
        double result = c.computeAverageLocalOfObservations(); // KSG already returns nats.
        if (!Double.isFinite(result)) throw new IllegalStateException("Nonfinite JIDT KSG result");
        return result; // Retain negative finite-sample estimates without clipping.
    }
}
