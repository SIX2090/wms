package androidx.compose.ui.node;

import kotlin.Metadata;

/* compiled from: MyersDiff.kt */
@Metadata(d1 = {"\u00002\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\b\n\u0002\b\u0005\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u0015\n\u0002\b\u0015\u001a\u0018\u0010\u0000\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u00032\u0006\u0010\u0004\u001a\u00020\u0005H\u0002\u001aZ\u0010\u0006\u001a\u00020\u00072\u0006\u0010\b\u001a\u00020\t2\u0006\u0010\n\u001a\u00020\t2\u0006\u0010\u000b\u001a\u00020\t2\u0006\u0010\f\u001a\u00020\t2\u0006\u0010\r\u001a\u00020\u00052\u0006\u0010\u000e\u001a\u00020\u000f2\u0006\u0010\u0006\u001a\u00020\u000f2\u0006\u0010\u0010\u001a\u00020\t2\u0006\u0010\u0011\u001a\u00020\u0012H\u0002ø\u0001\u0000¢\u0006\u0004\b\u0013\u0010\u0014\u001a \u0010\u0015\u001a\u00020\u00032\u0006\u0010\u0016\u001a\u00020\t2\u0006\u0010\u0017\u001a\u00020\t2\u0006\u0010\r\u001a\u00020\u0005H\u0002\u001a \u0010\u0018\u001a\u00020\u00012\u0006\u0010\u0016\u001a\u00020\t2\u0006\u0010\u0017\u001a\u00020\t2\u0006\u0010\u0004\u001a\u00020\u0005H\u0000\u001a8\u0010\u0019\u001a\u00020\u00012\u0006\u0010\u001a\u001a\u00020\t2\u0006\u0010\u001b\u001a\u00020\t2\u0006\u0010\u001c\u001a\u00020\t2\u0006\u0010\u001d\u001a\u00020\t2\u0006\u0010\u001e\u001a\u00020\u00072\u0006\u0010\u001f\u001a\u00020\u0012H\u0000\u001aZ\u0010\u000e\u001a\u00020\u00072\u0006\u0010\b\u001a\u00020\t2\u0006\u0010\n\u001a\u00020\t2\u0006\u0010\u000b\u001a\u00020\t2\u0006\u0010\f\u001a\u00020\t2\u0006\u0010\r\u001a\u00020\u00052\u0006\u0010\u000e\u001a\u00020\u000f2\u0006\u0010\u0006\u001a\u00020\u000f2\u0006\u0010\u0010\u001a\u00020\t2\u0006\u0010\u0011\u001a\u00020\u0012H\u0002ø\u0001\u0000¢\u0006\u0004\b \u0010\u0014\u001aR\u0010!\u001a\u00020\u00072\u0006\u0010\b\u001a\u00020\t2\u0006\u0010\n\u001a\u00020\t2\u0006\u0010\u000b\u001a\u00020\t2\u0006\u0010\f\u001a\u00020\t2\u0006\u0010\r\u001a\u00020\u00052\u0006\u0010\u000e\u001a\u00020\u000f2\u0006\u0010\u0006\u001a\u00020\u000f2\u0006\u0010\u0011\u001a\u00020\u0012H\u0002ø\u0001\u0000¢\u0006\u0004\b\"\u0010#\u001a\u001c\u0010$\u001a\u00020\u0001*\u00020\u00122\u0006\u0010%\u001a\u00020\t2\u0006\u0010&\u001a\u00020\tH\u0002\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006'"}, d2 = {"applyDiff", "", "diagonals", "Landroidx/compose/ui/node/IntStack;", "callback", "Landroidx/compose/ui/node/DiffCallback;", "backward", "", "oldStart", "", "oldEnd", "newStart", "newEnd", "cb", "forward", "Landroidx/compose/ui/node/CenteredArray;", "d", "snake", "", "backward-4l5_RBY", "(IIIILandroidx/compose/ui/node/DiffCallback;[I[II[I)Z", "calculateDiff", "oldSize", "newSize", "executeDiff", "fillSnake", "startX", "startY", "endX", "endY", "reverse", "data", "forward-4l5_RBY", "midPoint", "midPoint-q5eDKzI", "(IIIILandroidx/compose/ui/node/DiffCallback;[I[I[I)Z", "swap", "i", "j", "ui_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class MyersDiffKt {
    private static final IntStack calculateDiff(int oldSize, int newSize, DiffCallback cb) {
        int[] snake;
        int oldEnd = ((oldSize + newSize) + 1) / 2;
        IntStack diagonals = new IntStack(oldEnd * 3);
        IntStack stack = new IntStack(oldEnd * 4);
        stack.pushRange(0, oldSize, 0, newSize);
        int[] forward = CenteredArray.m5106constructorimpl(new int[(oldEnd * 2) + 1]);
        int[] backward = CenteredArray.m5106constructorimpl(new int[(oldEnd * 2) + 1]);
        int[] snake2 = Snake.m5282constructorimpl(new int[5]);
        while (stack.isNotEmpty()) {
            int newEnd = stack.pop();
            int newStart = stack.pop();
            int oldEnd2 = stack.pop();
            int oldStart = stack.pop();
            int max = oldEnd;
            int[] forward2 = forward;
            int[] snake3 = snake2;
            boolean found = m5183midPointq5eDKzI(oldStart, oldEnd2, newStart, newEnd, cb, forward, backward, snake2);
            if (!found) {
                snake2 = snake3;
                oldEnd = max;
                forward = forward2;
            } else {
                if (Snake.m5285getDiagonalSizeimpl(snake3) <= 0) {
                    snake = snake3;
                } else {
                    snake = snake3;
                    Snake.m5280addDiagonalToStackimpl(snake, diagonals);
                }
                stack.pushRange(oldStart, Snake.m5290getStartXimpl(snake), newStart, Snake.m5291getStartYimpl(snake));
                stack.pushRange(Snake.m5286getEndXimpl(snake), oldEnd2, Snake.m5287getEndYimpl(snake), newEnd);
                snake2 = snake;
                oldEnd = max;
                forward = forward2;
            }
        }
        diagonals.sortDiagonals();
        diagonals.pushDiagonal(oldSize, newSize, 0);
        return diagonals;
    }

    private static final void applyDiff(IntStack diagonals, DiffCallback callback) {
        int posX = 0;
        int posY = 0;
        int i = 0;
        while (i < diagonals.getLastIndex()) {
            int startX = diagonals.get(i) - diagonals.get(i + 2);
            int startY = diagonals.get(i + 1) - diagonals.get(i + 2);
            int len = diagonals.get(i + 2);
            i += 3;
            while (posX < startX) {
                callback.remove(posY, posX);
                posX++;
            }
            while (posY < startY) {
                callback.insert(posY);
                posY++;
            }
            while (true) {
                int len2 = len - 1;
                if (len > 0) {
                    callback.same(posX, posY);
                    posX++;
                    posY++;
                    len = len2;
                }
            }
        }
    }

    public static final void executeDiff(int oldSize, int newSize, DiffCallback callback) {
        IntStack diagonals = calculateDiff(oldSize, newSize, callback);
        applyDiff(diagonals, callback);
    }

    /* renamed from: midPoint-q5eDKzI, reason: not valid java name */
    private static final boolean m5183midPointq5eDKzI(int oldStart, int oldEnd, int newStart, int newEnd, DiffCallback cb, int[] forward, int[] backward, int[] snake) {
        int oldSize = oldEnd - oldStart;
        int newSize = newEnd - newStart;
        if (oldSize < 1 || newSize < 1) {
            return false;
        }
        int max = ((oldSize + newSize) + 1) / 2;
        CenteredArray.m5112setimpl(forward, 1, oldStart);
        CenteredArray.m5112setimpl(backward, 1, oldEnd);
        int d = 0;
        while (d < max) {
            int d2 = d;
            boolean found = m5182forward4l5_RBY(oldStart, oldEnd, newStart, newEnd, cb, forward, backward, d2, snake);
            if (found) {
                return true;
            }
            boolean found2 = m5181backward4l5_RBY(oldStart, oldEnd, newStart, newEnd, cb, forward, backward, d2, snake);
            if (found2) {
                return true;
            }
            d = d2 + 1;
        }
        return false;
    }

    /* renamed from: forward-4l5_RBY, reason: not valid java name */
    private static final boolean m5182forward4l5_RBY(int oldStart, int oldEnd, int newStart, int newEnd, DiffCallback cb, int[] forward, int[] backward, int d, int[] snake) {
        int startX;
        int x;
        int i = oldEnd;
        int oldSize = i - oldStart;
        int newSize = newEnd - newStart;
        int i2 = 1;
        boolean checkForSnake = Math.abs(oldSize - newSize) % 2 == 1;
        int delta = oldSize - newSize;
        int k = -d;
        while (k <= d) {
            if (k == (-d) || (k != d && CenteredArray.m5109getimpl(forward, k + 1) > CenteredArray.m5109getimpl(forward, k - 1))) {
                startX = CenteredArray.m5109getimpl(forward, k + 1);
                x = startX;
            } else {
                startX = CenteredArray.m5109getimpl(forward, k - 1);
                x = startX + 1;
            }
            int y = (newStart + (x - oldStart)) - k;
            int startY = (d == 0 || x != startX) ? y : y - 1;
            int startY2 = y;
            while (x < i && startY2 < newEnd) {
                if (!cb.areItemsTheSame(x, startY2)) {
                    break;
                }
                x++;
                startY2++;
            }
            CenteredArray.m5112setimpl(forward, k, x);
            if (checkForSnake) {
                int backwardsK = delta - k;
                if (backwardsK >= (-d) + i2 && backwardsK <= d - 1) {
                    if (CenteredArray.m5109getimpl(backward, backwardsK) > x) {
                        i2 = 1;
                    } else {
                        fillSnake(startX, startY, x, startY2, false, snake);
                        return true;
                    }
                }
            }
            k += 2;
            i = oldEnd;
        }
        return false;
    }

    /* renamed from: backward-4l5_RBY, reason: not valid java name */
    private static final boolean m5181backward4l5_RBY(int oldStart, int oldEnd, int newStart, int newEnd, DiffCallback cb, int[] forward, int[] backward, int d, int[] snake) {
        int startX;
        int x;
        int oldSize = oldEnd - oldStart;
        int newSize = newEnd - newStart;
        boolean checkForSnake = (oldSize - newSize) % 2 == 0;
        int delta = oldSize - newSize;
        for (int k = -d; k <= d; k += 2) {
            if (k == (-d) || (k != d && CenteredArray.m5109getimpl(backward, k + 1) < CenteredArray.m5109getimpl(backward, k - 1))) {
                startX = CenteredArray.m5109getimpl(backward, k + 1);
                x = startX;
            } else {
                startX = CenteredArray.m5109getimpl(backward, k - 1);
                x = startX - 1;
            }
            int y = newEnd - ((oldEnd - x) - k);
            int startY = (d == 0 || x != startX) ? y : y + 1;
            int y2 = y;
            while (x > oldStart && y2 > newStart) {
                if (!cb.areItemsTheSame(x - 1, y2 - 1)) {
                    break;
                }
                x--;
                y2--;
            }
            CenteredArray.m5112setimpl(backward, k, x);
            if (checkForSnake) {
                int forwardsK = delta - k;
                if (forwardsK >= (-d) && forwardsK <= d && CenteredArray.m5109getimpl(forward, forwardsK) >= x) {
                    fillSnake(x, y2, startX, startY, true, snake);
                    return true;
                }
            }
        }
        return false;
    }

    public static final void fillSnake(int i, int i2, int i3, int i4, boolean z, int[] iArr) {
        iArr[0] = i;
        iArr[1] = i2;
        iArr[2] = i3;
        iArr[3] = i4;
        iArr[4] = z ? 1 : 0;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final void swap(int[] $this$swap, int i, int j) {
        int tmp = $this$swap[i];
        $this$swap[i] = $this$swap[j];
        $this$swap[j] = tmp;
    }
}
