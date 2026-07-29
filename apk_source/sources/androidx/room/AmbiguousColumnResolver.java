package androidx.room;

import androidx.autofill.HintConstants;
import androidx.room.AmbiguousColumnResolver;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.NoSuchElementException;
import java.util.Set;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.collections.CollectionsKt;
import kotlin.collections.IntIterator;
import kotlin.collections.SetsKt;
import kotlin.jvm.JvmStatic;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function3;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;
import kotlin.jvm.internal.Ref;
import kotlin.ranges.IntRange;

/* compiled from: AmbiguousColumnResolver.kt */
@Metadata(d1 = {"\u0000L\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\u0002\n\u0002\b\u0002\n\u0002\u0010 \n\u0000\n\u0002\u0010!\n\u0000\n\u0002\u0010\b\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0011\n\u0002\u0010\u000e\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u0015\n\u0002\b\u0007\bÇ\u0002\u0018\u00002\u00020\u0001:\u0003\u001b\u001c\u001dB\u0007\b\u0002¢\u0006\u0002\u0010\u0002JV\u0010\u0003\u001a\u00020\u0004\"\u0004\b\u0000\u0010\u00052\u0012\u0010\u0006\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u0002H\u00050\u00070\u00072\u000e\b\u0002\u0010\b\u001a\b\u0012\u0004\u0012\u0002H\u00050\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\u0018\u0010\f\u001a\u0014\u0012\n\u0012\b\u0012\u0004\u0012\u0002H\u00050\u0007\u0012\u0004\u0012\u00020\u00040\rH\u0002JO\u0010\u000e\u001a\u00020\u00042\f\u0010\u0006\u001a\b\u0012\u0004\u0012\u00020\u000f0\u00072\f\u0010\u0010\u001a\b\u0012\u0004\u0012\u00020\u00120\u00112$\u0010\u0013\u001a \u0012\u0004\u0012\u00020\u000b\u0012\u0004\u0012\u00020\u000b\u0012\n\u0012\b\u0012\u0004\u0012\u00020\u000f0\u0007\u0012\u0004\u0012\u00020\u00040\u0014H\u0002¢\u0006\u0002\u0010\u0015J5\u0010\u0016\u001a\b\u0012\u0004\u0012\u00020\u00170\u00112\f\u0010\u0018\u001a\b\u0012\u0004\u0012\u00020\u00120\u00112\u0012\u0010\u0019\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\u00120\u00110\u0011H\u0007¢\u0006\u0002\u0010\u001a¨\u0006\u001e"}, d2 = {"Landroidx/room/AmbiguousColumnResolver;", "", "()V", "dfs", "", "T", "content", "", "current", "", "depth", "", "block", "Lkotlin/Function1;", "rabinKarpSearch", "Landroidx/room/AmbiguousColumnResolver$ResultColumn;", "pattern", "", "", "onHashMatch", "Lkotlin/Function3;", "(Ljava/util/List;[Ljava/lang/String;Lkotlin/jvm/functions/Function3;)V", "resolve", "", "resultColumns", "mappings", "([Ljava/lang/String;[[Ljava/lang/String;)[[I", "Match", "ResultColumn", "Solution", "room-common"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class AmbiguousColumnResolver {
    public static final AmbiguousColumnResolver INSTANCE = new AmbiguousColumnResolver();

    private AmbiguousColumnResolver() {
    }

    /* JADX WARN: Multi-variable type inference failed */
    /* JADX WARN: Type inference failed for: r1v5, types: [T, androidx.room.AmbiguousColumnResolver$Solution] */
    @JvmStatic
    public static final int[][] resolve(String[] resultColumns, String[][] mappings) {
        boolean z;
        Set requestedColumns;
        List usefulResultColumns;
        Object[] $this$forEachIndexed$iv;
        List usefulResultColumns2;
        List usefulResultColumns3;
        String str;
        Intrinsics.checkNotNullParameter(resultColumns, "resultColumns");
        Intrinsics.checkNotNullParameter(mappings, "mappings");
        int length = resultColumns.length;
        for (int i = 0; i < length; i++) {
            String column = resultColumns[i];
            if (column.charAt(0) == '`' && column.charAt(column.length() - 1) == '`') {
                str = column.substring(1, column.length() - 1);
                Intrinsics.checkNotNullExpressionValue(str, "this as java.lang.String…ing(startIndex, endIndex)");
            } else {
                str = column;
            }
            Locale US = Locale.US;
            Intrinsics.checkNotNullExpressionValue(US, "US");
            String lowerCase = str.toLowerCase(US);
            Intrinsics.checkNotNullExpressionValue(lowerCase, "this as java.lang.String).toLowerCase(locale)");
            resultColumns[i] = lowerCase;
        }
        int length2 = mappings.length;
        for (int i2 = 0; i2 < length2; i2++) {
            int length3 = mappings[i2].length;
            for (int j = 0; j < length3; j++) {
                String[] strArr = mappings[i2];
                String str2 = mappings[i2][j];
                Locale US2 = Locale.US;
                Intrinsics.checkNotNullExpressionValue(US2, "US");
                String lowerCase2 = str2.toLowerCase(US2);
                Intrinsics.checkNotNullExpressionValue(lowerCase2, "this as java.lang.String).toLowerCase(locale)");
                strArr[j] = lowerCase2;
            }
        }
        Set $this$resolve_u24lambda_u241 = SetsKt.createSetBuilder();
        String[][] $this$forEach$iv = mappings;
        for (Object element$iv : $this$forEach$iv) {
            String[] it = (String[]) element$iv;
            CollectionsKt.addAll($this$resolve_u24lambda_u241, it);
        }
        Set requestedColumns2 = SetsKt.build($this$resolve_u24lambda_u241);
        List $this$resolve_u24lambda_u243 = CollectionsKt.createListBuilder();
        int index$iv = 0;
        int length4 = resultColumns.length;
        int i3 = 0;
        while (i3 < length4) {
            String str3 = resultColumns[i3];
            int index$iv2 = index$iv + 1;
            if (requestedColumns2.contains(str3)) {
                $this$resolve_u24lambda_u243.add(new ResultColumn(str3, index$iv));
            }
            i3++;
            index$iv = index$iv2;
        }
        List $this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u246 = CollectionsKt.build($this$resolve_u24lambda_u243);
        int length5 = mappings.length;
        ArrayList arrayList = new ArrayList(length5);
        for (int i4 = 0; i4 < length5; i4++) {
            arrayList.add(new ArrayList());
        }
        final ArrayList mappingMatches = arrayList;
        String[][] $this$forEachIndexed$iv2 = mappings;
        final int index$iv3 = 0;
        int length6 = $this$forEachIndexed$iv2.length;
        int i5 = 0;
        while (i5 < length6) {
            Object item$iv = $this$forEachIndexed$iv2[i5];
            int index$iv4 = index$iv3 + 1;
            final String[] mapping = (String[]) item$iv;
            INSTANCE.rabinKarpSearch($this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u246, mapping, new Function3<Integer, Integer, List<? extends ResultColumn>, Unit>() { // from class: androidx.room.AmbiguousColumnResolver$resolve$1$1
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                /* JADX WARN: Multi-variable type inference failed */
                {
                    super(3);
                }

                @Override // kotlin.jvm.functions.Function3
                public /* bridge */ /* synthetic */ Unit invoke(Integer num, Integer num2, List<? extends AmbiguousColumnResolver.ResultColumn> list) {
                    invoke(num.intValue(), num2.intValue(), (List<AmbiguousColumnResolver.ResultColumn>) list);
                    return Unit.INSTANCE;
                }

                public final void invoke(int startIndex, int endIndex, List<AmbiguousColumnResolver.ResultColumn> list) {
                    Object element$iv2;
                    Iterable resultColumnsSublist = list;
                    Intrinsics.checkNotNullParameter(resultColumnsSublist, "resultColumnsSublist");
                    Object[] $this$map$iv = mapping;
                    Collection destination$iv$iv = new ArrayList($this$map$iv.length);
                    int length7 = $this$map$iv.length;
                    int i6 = 0;
                    while (i6 < length7) {
                        Object item$iv$iv = $this$map$iv[i6];
                        Iterable $this$firstOrNull$iv = resultColumnsSublist;
                        Iterator it2 = $this$firstOrNull$iv.iterator();
                        while (true) {
                            if (it2.hasNext()) {
                                element$iv2 = it2.next();
                                String resultColumnName = ((AmbiguousColumnResolver.ResultColumn) element$iv2).getName();
                                if (Intrinsics.areEqual(item$iv$iv, resultColumnName)) {
                                    break;
                                }
                            } else {
                                element$iv2 = null;
                                break;
                            }
                        }
                        AmbiguousColumnResolver.ResultColumn resultColumn = (AmbiguousColumnResolver.ResultColumn) element$iv2;
                        if (resultColumn == null) {
                            return;
                        }
                        destination$iv$iv.add(Integer.valueOf(resultColumn.getIndex()));
                        i6++;
                        resultColumnsSublist = list;
                    }
                    List resultIndices = (List) destination$iv$iv;
                    mappingMatches.get(index$iv3).add(new AmbiguousColumnResolver.Match(new IntRange(startIndex, endIndex - 1), resultIndices));
                }
            });
            if (((List) mappingMatches.get(index$iv3)).isEmpty()) {
                Collection destination$iv$iv = new ArrayList(mapping.length);
                String[] strArr2 = mapping;
                requestedColumns = requestedColumns2;
                int length7 = strArr2.length;
                $this$forEachIndexed$iv = $this$forEachIndexed$iv2;
                int i6 = 0;
                while (i6 < length7) {
                    String mappingColumnName = strArr2[i6];
                    List createListBuilder = CollectionsKt.createListBuilder();
                    List $this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u2462 = createListBuilder;
                    for (Object element$iv2 : $this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u246) {
                        ResultColumn resultColumn = (ResultColumn) element$iv2;
                        String[] strArr3 = strArr2;
                        int i7 = length7;
                        String mappingColumnName2 = mappingColumnName;
                        if (Intrinsics.areEqual(mappingColumnName2, resultColumn.getName())) {
                            usefulResultColumns2 = $this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u246;
                            usefulResultColumns3 = $this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u2462;
                            usefulResultColumns3.add(Integer.valueOf(resultColumn.getIndex()));
                        } else {
                            usefulResultColumns2 = $this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u246;
                            usefulResultColumns3 = $this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u2462;
                        }
                        $this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u2462 = usefulResultColumns3;
                        $this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u246 = usefulResultColumns2;
                        strArr2 = strArr3;
                        mappingColumnName = mappingColumnName2;
                        length7 = i7;
                    }
                    String[] strArr4 = strArr2;
                    int i8 = length7;
                    String mappingColumnName3 = mappingColumnName;
                    List usefulResultColumns4 = $this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u246;
                    List it2 = CollectionsKt.build(createListBuilder);
                    if (it2.isEmpty()) {
                        throw new IllegalStateException(("Column " + mappingColumnName3 + " not found in result").toString());
                    }
                    destination$iv$iv.add(it2);
                    i6++;
                    $this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u246 = usefulResultColumns4;
                    strArr2 = strArr4;
                    length7 = i8;
                }
                usefulResultColumns = $this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u246;
                List foundIndices = (List) destination$iv$iv;
                dfs$default(INSTANCE, foundIndices, null, 0, new Function1<List<? extends Integer>, Unit>() { // from class: androidx.room.AmbiguousColumnResolver$resolve$1$2
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    /* JADX WARN: Multi-variable type inference failed */
                    {
                        super(1);
                    }

                    @Override // kotlin.jvm.functions.Function1
                    public /* bridge */ /* synthetic */ Unit invoke(List<? extends Integer> list) {
                        invoke2((List<Integer>) list);
                        return Unit.INSTANCE;
                    }

                    /* renamed from: invoke, reason: avoid collision after fix types in other method */
                    public final void invoke2(List<Integer> indices) {
                        Intrinsics.checkNotNullParameter(indices, "indices");
                        Iterator<T> it3 = indices.iterator();
                        if (!it3.hasNext()) {
                            throw new NoSuchElementException();
                        }
                        int it4 = ((Number) it3.next()).intValue();
                        while (it3.hasNext()) {
                            int it5 = ((Number) it3.next()).intValue();
                            if (it4 > it5) {
                                it4 = it5;
                            }
                        }
                        int first = it4;
                        Iterator<T> it6 = indices.iterator();
                        if (!it6.hasNext()) {
                            throw new NoSuchElementException();
                        }
                        int it7 = ((Number) it6.next()).intValue();
                        while (it6.hasNext()) {
                            int it8 = ((Number) it6.next()).intValue();
                            if (it7 < it8) {
                                it7 = it8;
                            }
                        }
                        int last = it7;
                        mappingMatches.get(index$iv3).add(new AmbiguousColumnResolver.Match(new IntRange(first, last), indices));
                    }
                }, 6, null);
            } else {
                requestedColumns = requestedColumns2;
                usefulResultColumns = $this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u246;
                $this$forEachIndexed$iv = $this$forEachIndexed$iv2;
            }
            i5++;
            index$iv3 = index$iv4;
            requestedColumns2 = requestedColumns;
            $this$forEachIndexed$iv2 = $this$forEachIndexed$iv;
            $this$resolve_u24lambda_u2410_u24lambda_u249_u24lambda_u246 = usefulResultColumns;
        }
        ArrayList $this$all$iv = mappingMatches;
        if (!($this$all$iv instanceof Collection) || !$this$all$iv.isEmpty()) {
            Iterator it3 = $this$all$iv.iterator();
            while (true) {
                if (!it3.hasNext()) {
                    z = true;
                    break;
                }
                Object element$iv3 = it3.next();
                List it4 = (List) element$iv3;
                if (it4.isEmpty()) {
                    z = false;
                    break;
                }
            }
        } else {
            z = true;
        }
        if (!z) {
            throw new IllegalStateException("Failed to find matches for all mappings".toString());
        }
        final Ref.ObjectRef bestSolution = new Ref.ObjectRef();
        bestSolution.element = Solution.INSTANCE.getNO_SOLUTION();
        dfs$default(INSTANCE, mappingMatches, null, 0, new Function1<List<? extends Match>, Unit>() { // from class: androidx.room.AmbiguousColumnResolver$resolve$4
            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            {
                super(1);
            }

            @Override // kotlin.jvm.functions.Function1
            public /* bridge */ /* synthetic */ Unit invoke(List<? extends AmbiguousColumnResolver.Match> list) {
                invoke2((List<AmbiguousColumnResolver.Match>) list);
                return Unit.INSTANCE;
            }

            /* JADX WARN: Type inference failed for: r0v2, types: [T, androidx.room.AmbiguousColumnResolver$Solution] */
            /* renamed from: invoke, reason: avoid collision after fix types in other method */
            public final void invoke2(List<AmbiguousColumnResolver.Match> it5) {
                Intrinsics.checkNotNullParameter(it5, "it");
                ?? build = AmbiguousColumnResolver.Solution.INSTANCE.build(it5);
                if (build.compareTo(bestSolution.element) < 0) {
                    bestSolution.element = build;
                }
            }
        }, 6, null);
        Iterable $this$map$iv = ((Solution) bestSolution.element).getMatches();
        Collection destination$iv$iv2 = new ArrayList(CollectionsKt.collectionSizeOrDefault($this$map$iv, 10));
        for (Object item$iv$iv : $this$map$iv) {
            Match it5 = (Match) item$iv$iv;
            destination$iv$iv2.add(CollectionsKt.toIntArray(it5.getResultIndices()));
        }
        Collection thisCollection$iv = (List) destination$iv$iv2;
        return (int[][]) thisCollection$iv.toArray(new int[0][]);
    }

    private final void rabinKarpSearch(List<ResultColumn> content, String[] pattern, Function3<? super Integer, ? super Integer, ? super List<ResultColumn>, Unit> onHashMatch) {
        int rollingHash = 0;
        int i = 0;
        for (String it : pattern) {
            i += it.hashCode();
        }
        int mappingHash = i;
        int startIndex = 0;
        int endIndex = pattern.length;
        for (ResultColumn it2 : content.subList(0, endIndex)) {
            rollingHash += it2.getName().hashCode();
        }
        while (true) {
            if (mappingHash == rollingHash) {
                onHashMatch.invoke(Integer.valueOf(startIndex), Integer.valueOf(endIndex), content.subList(startIndex, endIndex));
            }
            startIndex++;
            endIndex++;
            if (endIndex <= content.size()) {
                rollingHash = (rollingHash - content.get(startIndex - 1).getName().hashCode()) + content.get(endIndex - 1).getName().hashCode();
            } else {
                return;
            }
        }
    }

    static /* synthetic */ void dfs$default(AmbiguousColumnResolver ambiguousColumnResolver, List list, List list2, int i, Function1 function1, int i2, Object obj) {
        if ((i2 & 2) != 0) {
            list2 = new ArrayList();
        }
        if ((i2 & 4) != 0) {
            i = 0;
        }
        ambiguousColumnResolver.dfs(list, list2, i, function1);
    }

    private final <T> void dfs(List<? extends List<? extends T>> content, List<T> current, int depth, Function1<? super List<? extends T>, Unit> block) {
        if (depth == content.size()) {
            block.invoke(CollectionsKt.toList(current));
            return;
        }
        Iterable $this$forEach$iv = content.get(depth);
        Iterator<T> it = $this$forEach$iv.iterator();
        while (it.hasNext()) {
            current.add(it.next());
            INSTANCE.dfs(content, current, depth + 1, block);
            CollectionsKt.removeLast(current);
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* compiled from: AmbiguousColumnResolver.kt */
    @Metadata(d1 = {"\u0000 \n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\b\n\u0002\b\t\n\u0002\u0010\u000b\n\u0002\b\u0004\b\u0082\b\u0018\u00002\u00020\u0001B\u0015\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005¢\u0006\u0002\u0010\u0006J\t\u0010\u000b\u001a\u00020\u0003HÆ\u0003J\t\u0010\f\u001a\u00020\u0005HÆ\u0003J\u001d\u0010\r\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u0005HÆ\u0001J\u0013\u0010\u000e\u001a\u00020\u000f2\b\u0010\u0010\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010\u0011\u001a\u00020\u0005HÖ\u0001J\t\u0010\u0012\u001a\u00020\u0003HÖ\u0001R\u0011\u0010\u0004\u001a\u00020\u0005¢\u0006\b\n\u0000\u001a\u0004\b\u0007\u0010\bR\u0011\u0010\u0002\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\t\u0010\n¨\u0006\u0013"}, d2 = {"Landroidx/room/AmbiguousColumnResolver$ResultColumn;", "", HintConstants.AUTOFILL_HINT_NAME, "", "index", "", "(Ljava/lang/String;I)V", "getIndex", "()I", "getName", "()Ljava/lang/String;", "component1", "component2", "copy", "equals", "", "other", "hashCode", "toString", "room-common"}, k = 1, mv = {1, 8, 0}, xi = 48)
    static final /* data */ class ResultColumn {
        private final int index;
        private final String name;

        public static /* synthetic */ ResultColumn copy$default(ResultColumn resultColumn, String str, int i, int i2, Object obj) {
            if ((i2 & 1) != 0) {
                str = resultColumn.name;
            }
            if ((i2 & 2) != 0) {
                i = resultColumn.index;
            }
            return resultColumn.copy(str, i);
        }

        /* renamed from: component1, reason: from getter */
        public final String getName() {
            return this.name;
        }

        /* renamed from: component2, reason: from getter */
        public final int getIndex() {
            return this.index;
        }

        public final ResultColumn copy(String name, int index) {
            Intrinsics.checkNotNullParameter(name, "name");
            return new ResultColumn(name, index);
        }

        public boolean equals(Object other) {
            if (this == other) {
                return true;
            }
            if (!(other instanceof ResultColumn)) {
                return false;
            }
            ResultColumn resultColumn = (ResultColumn) other;
            return Intrinsics.areEqual(this.name, resultColumn.name) && this.index == resultColumn.index;
        }

        public int hashCode() {
            return (this.name.hashCode() * 31) + Integer.hashCode(this.index);
        }

        public String toString() {
            return "ResultColumn(name=" + this.name + ", index=" + this.index + ')';
        }

        public ResultColumn(String name, int index) {
            Intrinsics.checkNotNullParameter(name, "name");
            this.name = name;
            this.index = index;
        }

        public final int getIndex() {
            return this.index;
        }

        public final String getName() {
            return this.name;
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* compiled from: AmbiguousColumnResolver.kt */
    @Metadata(d1 = {"\u0000\u001c\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010 \n\u0002\u0010\b\n\u0002\b\u0006\b\u0002\u0018\u00002\u00020\u0001B\u001b\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\f\u0010\u0004\u001a\b\u0012\u0004\u0012\u00020\u00060\u0005¢\u0006\u0002\u0010\u0007R\u0017\u0010\u0004\u001a\b\u0012\u0004\u0012\u00020\u00060\u0005¢\u0006\b\n\u0000\u001a\u0004\b\b\u0010\tR\u0011\u0010\u0002\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\n\u0010\u000b¨\u0006\f"}, d2 = {"Landroidx/room/AmbiguousColumnResolver$Match;", "", "resultRange", "Lkotlin/ranges/IntRange;", "resultIndices", "", "", "(Lkotlin/ranges/IntRange;Ljava/util/List;)V", "getResultIndices", "()Ljava/util/List;", "getResultRange", "()Lkotlin/ranges/IntRange;", "room-common"}, k = 1, mv = {1, 8, 0}, xi = 48)
    static final class Match {
        private final List<Integer> resultIndices;
        private final IntRange resultRange;

        public Match(IntRange resultRange, List<Integer> resultIndices) {
            Intrinsics.checkNotNullParameter(resultRange, "resultRange");
            Intrinsics.checkNotNullParameter(resultIndices, "resultIndices");
            this.resultRange = resultRange;
            this.resultIndices = resultIndices;
        }

        public final IntRange getResultRange() {
            return this.resultRange;
        }

        public final List<Integer> getResultIndices() {
            return this.resultIndices;
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* compiled from: AmbiguousColumnResolver.kt */
    @Metadata(d1 = {"\u0000\u001c\n\u0002\u0018\u0002\n\u0002\u0010\u000f\n\u0000\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\b\n\u0002\b\u000b\b\u0002\u0018\u0000 \u00102\b\u0012\u0004\u0012\u00020\u00000\u0001:\u0001\u0010B#\u0012\f\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00040\u0003\u0012\u0006\u0010\u0005\u001a\u00020\u0006\u0012\u0006\u0010\u0007\u001a\u00020\u0006¢\u0006\u0002\u0010\bJ\u0011\u0010\u000e\u001a\u00020\u00062\u0006\u0010\u000f\u001a\u00020\u0000H\u0096\u0002R\u0011\u0010\u0005\u001a\u00020\u0006¢\u0006\b\n\u0000\u001a\u0004\b\t\u0010\nR\u0017\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00040\u0003¢\u0006\b\n\u0000\u001a\u0004\b\u000b\u0010\fR\u0011\u0010\u0007\u001a\u00020\u0006¢\u0006\b\n\u0000\u001a\u0004\b\r\u0010\n¨\u0006\u0011"}, d2 = {"Landroidx/room/AmbiguousColumnResolver$Solution;", "", "matches", "", "Landroidx/room/AmbiguousColumnResolver$Match;", "coverageOffset", "", "overlaps", "(Ljava/util/List;II)V", "getCoverageOffset", "()I", "getMatches", "()Ljava/util/List;", "getOverlaps", "compareTo", "other", "Companion", "room-common"}, k = 1, mv = {1, 8, 0}, xi = 48)
    static final class Solution implements Comparable<Solution> {

        /* renamed from: Companion, reason: from kotlin metadata */
        public static final Companion INSTANCE = new Companion(null);
        private static final Solution NO_SOLUTION = new Solution(CollectionsKt.emptyList(), Integer.MAX_VALUE, Integer.MAX_VALUE);
        private final int coverageOffset;
        private final List<Match> matches;
        private final int overlaps;

        public Solution(List<Match> matches, int coverageOffset, int overlaps) {
            Intrinsics.checkNotNullParameter(matches, "matches");
            this.matches = matches;
            this.coverageOffset = coverageOffset;
            this.overlaps = overlaps;
        }

        public final List<Match> getMatches() {
            return this.matches;
        }

        public final int getCoverageOffset() {
            return this.coverageOffset;
        }

        public final int getOverlaps() {
            return this.overlaps;
        }

        @Override // java.lang.Comparable
        public int compareTo(Solution other) {
            Intrinsics.checkNotNullParameter(other, "other");
            int overlapCmp = Intrinsics.compare(this.overlaps, other.overlaps);
            if (overlapCmp != 0) {
                return overlapCmp;
            }
            return Intrinsics.compare(this.coverageOffset, other.coverageOffset);
        }

        /* compiled from: AmbiguousColumnResolver.kt */
        @Metadata(d1 = {"\u0000\u001e\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0000\b\u0086\u0003\u0018\u00002\u00020\u0001B\u0007\b\u0002¢\u0006\u0002\u0010\u0002J\u0014\u0010\u0007\u001a\u00020\u00042\f\u0010\b\u001a\b\u0012\u0004\u0012\u00020\n0\tR\u0011\u0010\u0003\u001a\u00020\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u0005\u0010\u0006¨\u0006\u000b"}, d2 = {"Landroidx/room/AmbiguousColumnResolver$Solution$Companion;", "", "()V", "NO_SOLUTION", "Landroidx/room/AmbiguousColumnResolver$Solution;", "getNO_SOLUTION", "()Landroidx/room/AmbiguousColumnResolver$Solution;", "build", "matches", "", "Landroidx/room/AmbiguousColumnResolver$Match;", "room-common"}, k = 1, mv = {1, 8, 0}, xi = 48)
        public static final class Companion {
            public /* synthetic */ Companion(DefaultConstructorMarker defaultConstructorMarker) {
                this();
            }

            private Companion() {
            }

            public final Solution getNO_SOLUTION() {
                return Solution.NO_SOLUTION;
            }

            public final Solution build(List<Match> matches) {
                int overlaps;
                boolean z;
                Intrinsics.checkNotNullParameter(matches, "matches");
                int i = 0;
                for (Match it : matches) {
                    i += ((it.getResultRange().getLast() - it.getResultRange().getFirst()) + 1) - it.getResultIndices().size();
                }
                int coverageOffset = i;
                Iterator<T> it2 = matches.iterator();
                if (!it2.hasNext()) {
                    throw new NoSuchElementException();
                }
                Match it3 = (Match) it2.next();
                int first = it3.getResultRange().getFirst();
                while (it2.hasNext()) {
                    Match it4 = (Match) it2.next();
                    int first2 = it4.getResultRange().getFirst();
                    if (first > first2) {
                        first = first2;
                    }
                }
                int min = first;
                Iterator<T> it5 = matches.iterator();
                if (!it5.hasNext()) {
                    throw new NoSuchElementException();
                }
                Match it6 = (Match) it5.next();
                int last = it6.getResultRange().getLast();
                while (it5.hasNext()) {
                    Match it7 = (Match) it5.next();
                    int last2 = it7.getResultRange().getLast();
                    if (last < last2) {
                        last = last2;
                    }
                }
                int max = last;
                Iterable $this$count$iv = new IntRange(min, max);
                if (($this$count$iv instanceof Collection) && ((Collection) $this$count$iv).isEmpty()) {
                    overlaps = 0;
                } else {
                    int count$iv = 0;
                    Iterator it8 = $this$count$iv.iterator();
                    while (it8.hasNext()) {
                        int element$iv = ((IntIterator) it8).nextInt();
                        int count = 0;
                        List<Match> $this$forEach$iv = matches;
                        Iterator it9 = $this$forEach$iv.iterator();
                        while (true) {
                            if (!it9.hasNext()) {
                                z = false;
                                break;
                            }
                            Object element$iv2 = it9.next();
                            Match it10 = (Match) element$iv2;
                            if (it10.getResultRange().contains(element$iv)) {
                                count++;
                            }
                            if (count > 1) {
                                z = true;
                                break;
                            }
                        }
                        if (z && (count$iv = count$iv + 1) < 0) {
                            CollectionsKt.throwCountOverflow();
                        }
                    }
                    overlaps = count$iv;
                }
                return new Solution(matches, coverageOffset, overlaps);
            }
        }
    }
}
