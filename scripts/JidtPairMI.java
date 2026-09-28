// Compute every eligible pair using the unmodified JIDT library, not a reimplementation.
import infodynamics.measures.discrete.MutualInformationCalculatorDiscrete;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

public final class JidtPairMI {
    public static void main(String[] args) throws Exception {
        if (args.length != 6) throw new IllegalArgumentException("WORK N T MIN_OVERLAP BINS THREADS");
        Path work = Paths.get(args[0]);
        int houses = Integer.parseInt(args[1]), times = Integer.parseInt(args[2]);
        int minimum = Integer.parseInt(args[3]), base = Integer.parseInt(args[4]);
        int threads = Integer.parseInt(args[5]);
        long pairCount = (long) houses * (houses - 1) / 2;
        if (houses < 2 || times < 2 || times > 65535 || minimum < 2 || minimum > times ||
            base < 2 || base > 32 || threads < 1 || pairCount > Integer.MAX_VALUE)
            throw new IllegalArgumentException("Invalid dimensions or settings");
        byte[] raw = Files.readAllBytes(work.resolve("bins.bin"));
        if (raw.length != (long) houses * times) throw new IllegalArgumentException("Wrong bins byte length");
        byte[][] bins = new byte[houses][];
        for (byte code : raw)
            if (code < -1 || code >= base) throw new IllegalArgumentException("Invalid bin code");
        for (int i = 0; i < houses; i++) bins[i] = Arrays.copyOfRange(raw, i * times, (i + 1) * times);
        float[] result = new float[(int) pairCount];
        Arrays.fill(result, Float.NaN);
        AtomicInteger nextRow = new AtomicInteger(), finishedRows = new AtomicInteger();
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        List<Future<?>> tasks = new ArrayList<>();
        try {
            for (int worker = 0; worker < threads; worker++) tasks.add(pool.submit(() -> {
                try {
                    MutualInformationCalculatorDiscrete calculator = new MutualInformationCalculatorDiscrete(base, base, 0);
                    int[] x = new int[times], y = new int[times];
                    // Reuse exact-length arrays: JIDT addObservations consumes the entire array.
                    int[][] xByLength = new int[times + 1][], yByLength = new int[times + 1][];
                    for (int i; (i = nextRow.getAndIncrement()) < houses - 1;) {
                        int offset = (int) ((long) i * (2L * houses - i - 1) / 2);
                        for (int j = i + 1; j < houses; j++, offset++) {
                            int count = 0;
                            for (int t = 0; t < times; t++) {
                                int a = bins[i][t], b = bins[j][t];
                                if (a >= 0 && b >= 0) { x[count] = a; y[count] = b; count++; }
                            }
                            if (count < minimum) continue;
                            if (xByLength[count] == null) {
                                xByLength[count] = new int[count]; yByLength[count] = new int[count];
                            }
                            System.arraycopy(x, 0, xByLength[count], 0, count);
                            System.arraycopy(y, 0, yByLength[count], 0, count);
                            calculator.initialise();
                            calculator.addObservations(xByLength[count], yByLength[count]);
                            // JIDT's discrete estimator returns bits; keep this project's nats convention.
                            double nats = calculator.computeAverageLocalOfObservations() * Math.log(2.0);
                            if (!Double.isFinite(nats) || nats < -1e-12)
                                throw new IllegalStateException("Invalid JIDT estimate");
                            result[offset] = (float) Math.max(0.0, nats);
                        }
                        int done = finishedRows.incrementAndGet();
                        if (done % 512 == 0) System.out.println("JIDT rows complete: " + done + "/" + (houses - 1));
                    }
                } catch (Exception failure) { throw new RuntimeException(failure); }
            }));
            for (Future<?> task : tasks) task.get();
        } finally { pool.shutdownNow(); }
        Path destination = work.resolve("mutual_information.bin");
        ByteBuffer buffer = ByteBuffer.allocate(1024 * 1024).order(ByteOrder.LITTLE_ENDIAN);
        try (FileChannel channel = FileChannel.open(destination, StandardOpenOption.CREATE,
                StandardOpenOption.TRUNCATE_EXISTING, StandardOpenOption.WRITE)) {
            for (float value : result) {
                if (buffer.remaining() < 4) { buffer.flip(); while (buffer.hasRemaining()) channel.write(buffer); buffer.clear(); }
                buffer.putFloat(value);
            }
            buffer.flip(); while (buffer.hasRemaining()) channel.write(buffer);
        }
        System.out.println("JIDT computed " + pairCount + " pair slots (bits converted to nats)");
    }
}
