//! Exercise the public safe APIs affected by RUSTSEC-2024-0429 using optimized
//! code. No GUI, GTK initialization or application state is involved.

#[cfg(test)]
mod tests {
    use glib::{prelude::*, Variant};

    const VALUES: [&str; 6] = ["alpha", "βeta", "gamma", "δelta", "epsilon", "omega"];

    fn sample() -> Variant {
        VALUES.to_vec().to_variant()
    }

    #[test]
    fn optimized_profile_is_required() {
        assert!(
            !cfg!(debug_assertions),
            "This regression must run with cargo test --release; debug builds hide the original UB"
        );
    }

    #[test]
    fn forward_iteration_reads_every_string_including_unicode() {
        let variant = sample();
        let mut strings = variant.array_iter_str().unwrap();
        assert_eq!(strings.size_hint(), (VALUES.len(), Some(VALUES.len())));
        for (index, expected) in VALUES.into_iter().enumerate() {
            assert_eq!(strings.next(), Some(expected));
            assert_eq!(strings.len(), VALUES.len() - index - 1);
        }
        assert_eq!(strings.next(), None);
        assert_eq!(strings.next_back(), None);
        assert_eq!(
            variant.array_iter_str().unwrap().collect::<Vec<_>>(),
            VALUES
        );
    }

    #[test]
    fn backward_iteration_reads_every_string_including_unicode() {
        let variant = sample();
        let mut strings = variant.array_iter_str().unwrap();
        for expected in VALUES.into_iter().rev() {
            assert_eq!(strings.next_back(), Some(expected));
        }
        assert_eq!(strings.len(), 0);
        assert_eq!(strings.next_back(), None);
        assert_eq!(strings.next(), None);
    }

    #[test]
    fn nth_and_last_use_valid_out_parameter_storage() {
        let variant = sample();
        let mut strings = variant.array_iter_str().unwrap();
        assert_eq!(strings.nth(0), Some("alpha"));
        assert_eq!(strings.nth(1), Some("gamma"));
        assert_eq!(strings.len(), 3);
        assert_eq!(strings.nth(usize::MAX), None);
        assert_eq!(strings.next(), None);
        assert_eq!(variant.array_iter_str().unwrap().last(), Some("omega"));
    }

    #[test]
    fn nth_back_and_mixed_ends_preserve_remaining_items() {
        let variant = sample();
        let mut strings = variant.array_iter_str().unwrap();
        assert_eq!(strings.next(), Some("alpha"));
        assert_eq!(strings.next_back(), Some("omega"));
        assert_eq!(strings.nth(1), Some("gamma"));
        assert_eq!(strings.nth_back(1), Some("δelta"));
        assert_eq!(strings.len(), 0);
        assert_eq!(strings.size_hint(), (0, Some(0)));
        assert_eq!(strings.nth_back(usize::MAX), None);
        assert_eq!(strings.next(), None);
        assert_eq!(strings.next_back(), None);
    }

    #[test]
    fn empty_and_singleton_iterators_are_fused_at_both_ends() {
        let empty = Vec::<String>::new().to_variant();
        let mut strings = empty.array_iter_str().unwrap();
        assert_eq!(strings.len(), 0);
        assert_eq!(strings.next(), None);
        assert_eq!(strings.next_back(), None);
        assert_eq!(strings.nth(usize::MAX), None);
        assert_eq!(strings.nth_back(usize::MAX), None);
        assert_eq!(empty.array_iter_str().unwrap().last(), None);

        let single = vec!["only"].to_variant();
        let mut strings = single.array_iter_str().unwrap();
        assert_eq!(strings.next_back(), Some("only"));
        assert_eq!(strings.len(), 0);
        assert_eq!(strings.next(), None);
        assert_eq!(strings.next_back(), None);
        assert_eq!(single.array_iter_str().unwrap().last(), Some("only"));
    }

    #[test]
    fn returned_strings_borrow_the_variant_and_outlive_the_iterator() {
        let variant = sample();
        let string = {
            let mut strings = variant.array_iter_str().unwrap();
            strings.nth(1).unwrap()
        };
        assert_eq!(string, "βeta");
        assert_eq!(variant.array_iter_str().unwrap().nth(1), Some(string));
    }
}
