import "slick-carousel/slick/slick.css";
import "slick-carousel/slick/slick-theme.css";
import React from "react";
import Slider from "react-slick";
import { FaChevronLeft, FaChevronRight } from "react-icons/fa";
import artistData from "./artistList";

function NextArrow({ onClick }) {
    return (
        <div
            onClick={onClick}
            className="flex items-center justify-center bg-black/70 rounded-full w-10 h-10 cursor-pointer hover:bg-black absolute top-1/2 right-4 transform -translate-y-1/2 z-10"
        >
            <FaChevronRight className="text-white text-lg" />
        </div>
    );
}

function PrevArrow({ onClick }) {
    return (
        <div
            onClick={onClick}
            className="flex items-center justify-center bg-black/70 rounded-full w-10 h-10 cursor-pointer hover:bg-black absolute top-1/2 left-4 transform -translate-y-1/2 z-10"
        >
            <FaChevronLeft className="text-white text-lg" />
        </div>
    );
}



function Gallery( {setArtistName}) {
    const settings = {
        dots: true,
        infinite: true,
        speed: 500,
        slidesToShow: 6,
        slidesToScroll: 3,
        nextArrow: <NextArrow />,
        prevArrow: <PrevArrow />,
    };
    return (
        <div className="slider-container pb-5">
            <Slider {...settings}>
                {artistData.map((artist) => (

                    <div className="bg-white w-full max-w-sm text-black rounded-xl shadow-md overflow-hidden">
                        <div className="w-full aspect-[4/5]">
                            <img
                                src={artist.img}
                                alt={artist.name}
                                className="w-full h-full object-cover" />
                        </div>
                        <div>
                            <p>{artist.name}</p>
                            <button onClick={() => {setArtistName(artist.name)}}>Select to search</button>
                        </div>
                    </div>
                ))}
            </Slider>
        </div>
    );
}

export default Gallery;
