import { DependencyList, useEffect, useState } from "react";

import { withInquiryCode } from "./client";

export type AsyncResource<T> = {
  data: T | null;
  error: string | null;
  isLoading: boolean;
};

export function useAsyncResource<T>(loader: () => Promise<T>, deps: DependencyList): AsyncResource<T> {
  const [state, setState] = useState<AsyncResource<T>>({
    data: null,
    error: null,
    isLoading: true,
  });

  useEffect(() => {
    let isCurrent = true;
    setState((current) => ({ ...current, error: null, isLoading: true }));

    loader()
      .then((data) => {
        if (isCurrent) setState({ data, error: null, isLoading: false });
      })
      .catch((error: unknown) => {
        if (isCurrent) {
          setState({
            data: null,
            error: withInquiryCode("정보를 불러오지 못했어요. 잠시 후 다시 시도해주세요.", error),
            isLoading: false,
          });
        }
      });

    return () => {
      isCurrent = false;
    };
  }, deps);

  return state;
}
