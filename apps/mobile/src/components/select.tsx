import { Check, ChevronDown } from 'lucide-react-native';
import { useState } from 'react';
import { FlatList, Modal, Pressable, StyleSheet, View } from 'react-native';

import { Txt } from '@/components/ui';
import { C, F, R, STROKE } from '@/constants/theme';

/** 스케치의 드롭다운(▽) */
export function Select<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: readonly T[];
  onChange: (v: T) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <View style={{ gap: 8 }}>
      <Txt variant="label" muted>
        {label}
      </Txt>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${label} 선택, 현재 ${value}`}
        onPress={() => setOpen(true)}
        style={({ pressed }) => [s.box, pressed && { borderColor: C.primary }]}>
        <Txt variant="bodyStrong" style={{ fontSize: 16 }}>
          {value}
        </Txt>
        <ChevronDown size={18} color={C.sub} strokeWidth={STROKE} />
      </Pressable>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={s.backdrop} onPress={() => setOpen(false)}>
          <View style={s.sheet}>
            <Txt variant="h2" style={{ paddingHorizontal: 22, paddingVertical: 16 }}>
              {label}
            </Txt>
            <FlatList
              data={options}
              keyExtractor={(o) => o}
              renderItem={({ item }) => {
                const selected = item === value;
                return (
                  <Pressable
                    style={({ pressed }) => [s.option, (pressed || selected) && { backgroundColor: C.accentSoft }]}
                    onPress={() => {
                      onChange(item);
                      setOpen(false);
                    }}>
                    <Txt
                      variant="body"
                      color={selected ? C.primary : C.text}
                      style={{ fontSize: 16, fontFamily: selected ? F.bold : F.medium }}>
                      {item}
                    </Txt>
                    {selected && <Check size={20} color={C.primary} strokeWidth={2.6} />}
                  </Pressable>
                );
              }}
            />
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  box: {
    minHeight: 52,
    borderWidth: 1.5,
    borderColor: C.border,
    borderRadius: R.field,
    paddingHorizontal: 16,
    backgroundColor: C.field,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  backdrop: { flex: 1, backgroundColor: C.scrim, justifyContent: 'center', padding: 24 },
  sheet: {
    backgroundColor: C.card,
    borderRadius: R.card,
    paddingBottom: 10,
    maxHeight: '70%',
    width: '100%',
    maxWidth: 420,
    alignSelf: 'center',
    overflow: 'hidden',
  },
  option: {
    minHeight: 52,
    marginHorizontal: 10,
    borderRadius: 16,
    paddingHorizontal: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
});
