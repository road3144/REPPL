package com.a401.reppl.service.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

import java.util.List;
import java.util.Map;

@Getter
@Builder
@AllArgsConstructor
public class JobCreateCommand {

    private final String videoKey;
    private final List<String> refImageKeys;
    private final RoiInfo roi;
    private final Map<String, Object> options;

    @Getter
    @Builder
    @AllArgsConstructor
    public static class RoiInfo {
        private final RoiFrame frame;
        private final String coordinateSystem;
        private final List<RoiBox> boxes;
    }

    @Getter
    @Builder
    @AllArgsConstructor
    public static class RoiFrame {
        private final String type;
        private final Long timestampMs;
    }

    @Getter
    @Builder
    @AllArgsConstructor
    public static class RoiBox {
        private final String id;
        private final Double x;
        private final Double y;
        private final Double w;
        private final Double h;
    }
}
